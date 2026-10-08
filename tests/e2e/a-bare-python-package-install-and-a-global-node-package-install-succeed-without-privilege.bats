#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design; run sets output and lines
# Feature 007 (prompt 04, slice 1, cycle 4), SC-6 (spec FR-25 to FR-31, D-12 to D-15; research R9;
# lore cross-stack P004, P005; nodejs Q001):
#   SC-6 "A bare Python package install and a global Node package install each succeed as the agent's user
#        without privilege and persist across new shells"
#
# In the running agent container, from outside (lore cross-stack P005), as the image's own user. Nothing
# here sets PIP_*, npm_config_* or PATH: the bare commands must work by what the image ships.
#
# Every cell is self-contained: its own directory under /tmp (container_tmpdir), and names and versions
# made fresh for it (tlprobe_<n>, tl-probe-<n>, version 1.0.<n>). A unique version per build is nodejs
# Q001: npm serves an unchanged version from its cache, so a reused one could pass on old bytes. The
# probes print text naming their own unique name, so what runs is what this cell built (P004). teardown
# uninstalls them, so nothing of one cell is on the agent's PATH for the next.
#
#   Python   a wheel built in the container by the test (python3 -I, stdlib zipfile: METADATA, WHEEL,
#            entry_points.txt with one console script, RECORD with real hashes), no network, installed
#            with a BARE `pip install --no-index <wheel>` (no --user). In a NEW docker exec, from /: the
#            module imports from /home/agent/.local/lib/python3.*/site-packages and its script resolves
#            to /home/agent/.local/bin and runs. pip must not say "Defaulting to user installation":
#            that is pip's own fallback for an unwritable site-packages, so seeing it would mean the user
#            location came from file permissions, not from the interpreter's configuration (FR-26).
#   Node     a package packed by the test (`npm pack --offline`), installed with a BARE
#            `npm install -g --offline <tgz>` (no --prefix). In a new exec its binary resolves to
#            /home/agent/.local/bin and prints its text; `npm prefix -g` is /home/agent/.local (FR-27).
#   Home     a marker is touched before both installs; afterwards `find / -xdev` (pruning /proc, /sys,
#            /dev, /run, /tmp and /home/agent) lists nothing newer. Nothing is allow-listed: anything else
#            that changed fails the cell and is printed. Unreadable directories are not reported (the
#            agent cannot write what it cannot list either).
#   timelike its interpreter's purelib (asked of /opt/timelike/python/bin/python3 -I via sysconfig) is
#            listed recursively, sorted, with size and mtime, before and after a bare pip install: equal.
#            `/opt/timelike/python/bin/python3 -I -c 'import <module>'` fails while the agent's python3
#            imports it (so the failure is not vacuous).
#   No PIP_BREAK_SYSTEM_PACKAGES in the environment of the style, in `pip config list`, or in any file
#            under /etc (profile.d, /etc/timelike and the hook included), the agent pip.conf or the
#            npmrc. Both of those must exist, so the search is not vacuous.
#   Runtimes python3, python, pip, pip3, node, npm, npx resolve to /usr/local/bin/<name> (D-12), whose
#            real path is inside the real path of /opt/agent/python or /opt/agent/node, under /opt/agent/,
#            and never under /opt/timelike or the real path of /opt/timelike/python (itself a link to a uv
#            directory). python3's sys.prefix is the agent prefix. No lib/python3.*/EXTERNALLY-MANAGED in
#            the agent prefix. Versions are pins.env's PYTHON_VERSION and NODE_VERSION, read on the runner
#            from the mounted repository (P004).
#
# Cells: bash -c and bash -lc in `notty`, the harness's own invocation.

load helpers

SC6_HOME=/home/agent

setup_file() {
  stamp_check
}

teardown() {
  if [[ -n "${SC6_MOD:-}" ]]; then
    exec_plain pip uninstall -y -q "$SC6_MOD" >/dev/null 2>&1 || true
  fi
  if [[ -n "${SC6_PKG:-}" ]]; then
    exec_plain npm uninstall -g --offline "$SC6_PKG" >/dev/null 2>&1 || true
  fi
  container_rm "${SC6_RM:-}"
}

# sc6_names — fresh names for one cell. The first digit is never 0: npm rejects a leading zero in a
# version's numeric part.
sc6_names() {
  local n="$((RANDOM % 9 + 1))${RANDOM}${RANDOM}"
  SC6_MOD="tlprobe_${n}"
  SC6_SCRIPT="tlprobe-py-${n}"
  SC6_PKG="tl-probe-${n}"
  SC6_BIN="tlprobe-js-${n}"
  SC6_VER="1.0.${n}"
}

# sc6_dir — a fresh directory for this cell, removed by teardown. Sets SC6_D.
sc6_dir() {
  SC6_D="$(container_tmpdir sc6)" || {
    echo "cannot make a directory under /tmp in ${AGENT_CONTAINER}" >&2
    return 1
  }
  SC6_RM="$SC6_D"
}

# pin_value KEY — KEY's value from pins.env, read on the runner from the mounted repository.
pin_value() {
  local pins="${BATS_TEST_DIRNAME}/../../pins.env" v
  [[ -f "$pins" ]] || { echo "no pins.env at ${pins}" >&2; return 1; }
  v="$(sed -n "s/^$1=//p" "$pins" | head -n 1)"
  [[ -n "$v" ]] || { echo "pins.env has no $1" >&2; return 1; }
  printf '%s' "$v"
}

# assert_matches KEY ERE — the value of KEY matches ERE.
assert_matches() {
  local got
  got="$(value_of "$1")"
  if ! [[ "$got" =~ $2 ]]; then
    printf '%s: %q does not match /%s/; output:\n%s\n' "$1" "$got" "$2" "$output" >&2
    return 1
  fi
}

# --- the installs (the commands under test) ------------------------------------------------------------
# SC6_INSTALL_PY — inputs SC6_D, SC6_MOD, SC6_VER, SC6_SCRIPT (passed with -e). Builds the wheel in
# SC6_D, then the bare install.
read -r -d '' SC6_INSTALL_PY <<'EOF' || true
printf "user=%s\n" "$(id -un)"
printf "uid=%s\n" "$(id -u)"
cd "$SC6_D" || { printf "cd=failed\n"; exit 3; }
whl="$(python3 -I -c '
import base64, hashlib, sys, zipfile
out, mod, ver, script = sys.argv[1:5]
di = "%s-%s.dist-info" % (mod, ver)
files = {
    mod + "/__init__.py": "def main():\n    print(\"tlprobe ran: %s\")\n" % mod,
    di + "/METADATA": "Metadata-Version: 2.1\nName: %s\nVersion: %s\n" % (mod, ver),
    di + "/WHEEL": "Wheel-Version: 1.0\nGenerator: timelike-e2e\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    di + "/entry_points.txt": "[console_scripts]\n%s = %s:main\n" % (script, mod),
}
record = []
for name, text in files.items():
    data = text.encode()
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    record.append("%s,sha256=%s,%d" % (name, digest, len(data)))
record.append(di + "/RECORD,,")
files[di + "/RECORD"] = "\n".join(record) + "\n"
path = "%s/%s-%s-py3-none-any.whl" % (out, mod, ver)
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
    for name, text in files.items():
        z.writestr(name, text)
print(path)
' "$SC6_D" "$SC6_MOD" "$SC6_VER" "$SC6_SCRIPT" 2>"$SC6_D/build.err")"
printf "build_rc=%s\n" "$?"
printf "build_err=%s\n" "$(head -c 300 "$SC6_D/build.err" | tr "\n" " ")"
pip install --no-index "$whl" >"$SC6_D/pip.out" 2>&1
printf "pip_rc=%s\n" "$?"
printf "pip_defaulted=%s\n" "$(grep -c "Defaulting to user installation" "$SC6_D/pip.out")"
printf "pip_out=%s\n" "$(tail -c 800 "$SC6_D/pip.out" | tr "\n" " ")"
printf "read=done\n"
EOF

# SC6_INSTALL_NODE — inputs SC6_D, SC6_PKG, SC6_VER, SC6_BIN. Packs the package in SC6_D/pkg, then the
# bare global install.
read -r -d '' SC6_INSTALL_NODE <<'EOF' || true
printf "user=%s\n" "$(id -un)"
printf "uid=%s\n" "$(id -u)"
mkdir "$SC6_D/pkg" && cd "$SC6_D/pkg" || { printf "cd=failed\n"; exit 3; }
printf '{"name": "%s", "version": "%s", "bin": {"%s": "cli.js"}}\n' "$SC6_PKG" "$SC6_VER" "$SC6_BIN" >package.json
printf '#!/usr/bin/env node\nconsole.log("tlprobe ran: %s");\n' "$SC6_BIN" >cli.js
chmod 0755 cli.js
npm pack --offline >"$SC6_D/pack.out" 2>&1
printf "pack_rc=%s\n" "$?"
printf "pack_out=%s\n" "$(tail -c 400 "$SC6_D/pack.out" | tr "\n" " ")"
tgz="$SC6_D/pkg/$SC6_PKG-$SC6_VER.tgz"
if [ -f "$tgz" ]; then printf "tgz=present\n"; else printf "tgz=absent\n"; fi
cd "$SC6_D" || exit 3
npm install -g --offline "$tgz" >"$SC6_D/npm.out" 2>&1
printf "npm_rc=%s\n" "$?"
printf "npm_out=%s\n" "$(tail -c 800 "$SC6_D/npm.out" | tr "\n" " ")"
printf "read=done\n"
EOF

# sc6_install_python STYLE — the bare pip install, under STYLE, as the image's user; must succeed.
sc6_install_python() {
  # shellcheck disable=SC2034 # read by exec_in and run_in (dynamic scope)
  local RUN_TIMEOUT=120 # an install, not a criterion bound; a hang still fails
  run_in -e "SC6_D=${SC6_D}" -e "SC6_MOD=${SC6_MOD}" -e "SC6_VER=${SC6_VER}" -e "SC6_SCRIPT=${SC6_SCRIPT}" \
    "$1" notty "$SC6_INSTALL_PY"
  assert_status 0
  assert_value read "done"
  assert_value user agent
  assert_matches uid '^[1-9][0-9]*$'
  assert_value build_rc 0
  assert_value pip_rc 0
  assert_value pip_defaulted 0
}

# sc6_install_node STYLE — the bare npm install -g, under STYLE, as the image's user; must succeed.
sc6_install_node() {
  # shellcheck disable=SC2034 # read by exec_in and run_in (dynamic scope)
  local RUN_TIMEOUT=120
  run_in -e "SC6_D=${SC6_D}" -e "SC6_PKG=${SC6_PKG}" -e "SC6_VER=${SC6_VER}" -e "SC6_BIN=${SC6_BIN}" \
    "$1" notty "$SC6_INSTALL_NODE"
  assert_status 0
  assert_value read "done"
  assert_value user agent
  assert_matches uid '^[1-9][0-9]*$'
  assert_value pack_rc 0
  assert_value tgz present
  assert_value npm_rc 0
}

# --- Python: installs, and persists into a new shell --------------------------------------------------
read -r -d '' SC6_AFTER_PY <<'EOF' || true
cd / || { printf "cd=failed\n"; exit 3; }
printf "home=%s\n" "$HOME"
printf "py_file=%s\n" "$(python3 -c "import ${SC6_MOD}; print(${SC6_MOD}.__file__)" 2>&1 | tr "\n" " " | sed "s/ *$//")"
printf "script_path=%s\n" "$(command -v "$SC6_SCRIPT")"
out="$("$SC6_SCRIPT" 2>&1)"
printf "script_rc=%s\n" "$?"
printf "script_out=%s\n" "$(printf "%s" "$out" | tr "\n" " ")"
printf "read=done\n"
EOF

check_python() {
  sc6_names
  sc6_dir
  sc6_install_python "$1"
  run_in -e "SC6_MOD=${SC6_MOD}" -e "SC6_SCRIPT=${SC6_SCRIPT}" "$1" notty "$SC6_AFTER_PY"
  assert_status 0
  assert_value read "done"
  assert_value home "$SC6_HOME"
  assert_matches py_file "^${SC6_HOME}/\\.local/lib/python3\\.[0-9]+/site-packages/${SC6_MOD}/__init__\\.py\$"
  assert_value script_path "${SC6_HOME}/.local/bin/${SC6_SCRIPT}"
  assert_value script_rc 0
  assert_value script_out "tlprobe ran: ${SC6_MOD}"
}

@test "SC-6 [bash -c, notty] A bare Python package install and a global Node package install each succeed as the agent's user without privilege and persist across new shells — Python: a bare pip install --no-index of a test-built wheel succeeds as agent; in a new shell, from /, it imports from ~/.local/lib and its console script runs from ~/.local/bin" { check_python c; }
@test "SC-6 [bash -lc, notty] A bare Python package install and a global Node package install each succeed as the agent's user without privilege and persist across new shells — Python: a bare pip install --no-index of a test-built wheel succeeds as agent; in a new shell, from /, it imports from ~/.local/lib and its console script runs from ~/.local/bin" { check_python lc; }

# --- Node: installs, and persists into a new shell ----------------------------------------------------
read -r -d '' SC6_AFTER_NODE <<'EOF' || true
cd / || { printf "cd=failed\n"; exit 3; }
printf "home=%s\n" "$HOME"
printf "bin_path=%s\n" "$(command -v "$SC6_BIN")"
out="$("$SC6_BIN" 2>&1)"
printf "bin_rc=%s\n" "$?"
printf "bin_out=%s\n" "$(printf "%s" "$out" | tr "\n" " ")"
if [ -d "$HOME/.local/lib/node_modules/$SC6_PKG" ]; then printf "module_dir=present\n"; else printf "module_dir=absent\n"; fi
printf "npm_prefix_g=%s\n" "$(npm prefix -g 2>/dev/null | tr "\n" " " | sed "s/ *$//")"
printf "read=done\n"
EOF

check_node() {
  sc6_names
  sc6_dir
  sc6_install_node "$1"
  run_in -e "SC6_PKG=${SC6_PKG}" -e "SC6_BIN=${SC6_BIN}" "$1" notty "$SC6_AFTER_NODE"
  assert_status 0
  assert_value read "done"
  assert_value home "$SC6_HOME"
  assert_value bin_path "${SC6_HOME}/.local/bin/${SC6_BIN}"
  assert_value bin_rc 0
  assert_value bin_out "tlprobe ran: ${SC6_BIN}"
  assert_value module_dir present
  assert_value npm_prefix_g "${SC6_HOME}/.local"
}

@test "SC-6 [bash -c, notty] A bare Python package install and a global Node package install each succeed as the agent's user without privilege and persist across new shells — Node: a bare npm install -g --offline of a test-packed package succeeds as agent; in a new shell its binary runs from ~/.local/bin" { check_node c; }
@test "SC-6 [bash -lc, notty] A bare Python package install and a global Node package install each succeed as the agent's user without privilege and persist across new shells — Node: a bare npm install -g --offline of a test-packed package succeeds as agent; in a new shell its binary runs from ~/.local/bin" { check_node lc; }

# --- only the agent's home changed --------------------------------------------------------------------
read -r -d '' SC6_CHANGED <<'EOF' || true
printf "home=%s\n" "$HOME"
find / -xdev \( -path /proc -o -path /sys -o -path /dev -o -path /run -o -path /tmp -o -path /home/agent \) -prune \
  -o -newer "$SC6_MARK" -print 2>/dev/null | head -n 50 | sed "s/^/changed=/"
printf "home_changed=%s\n" "$(find /home/agent -newer "$SC6_MARK" -print 2>/dev/null | wc -l)"
printf "read=done\n"
EOF

check_only_home() {
  sc6_names
  sc6_dir
  local mark="${SC6_D}/marker"
  exec_plain touch "$mark" || {
    echo "cannot write the marker ${mark} in ${AGENT_CONTAINER}" >&2
    return 1
  }
  sc6_install_python "$1"
  sc6_install_node "$1"
  run_in -e "SC6_MARK=${mark}" "$1" notty "$SC6_CHANGED"
  assert_status 0
  assert_value read "done"
  assert_value home "$SC6_HOME"
  local -a changed=()
  local line
  for line in "${lines[@]}"; do
    [[ "$line" == changed=* ]] && changed+=("${line#changed=}")
  done
  if ((${#changed[@]} > 0)); then
    printf 'outside %s, newer than the marker written before the installs (first 50):\n' "$SC6_HOME" >&2
    printf '  %s\n' "${changed[@]}" >&2
    return 1
  fi
  # Not vacuous: the installs did write, and into the home.
  assert_matches home_changed '^[1-9][0-9]*$'
}

@test "SC-6 [bash -c, notty] A bare Python package install and a global Node package install each succeed as the agent's user without privilege and persist across new shells — only the agent's home changed: after both installs nothing outside /home/agent (/proc, /sys, /dev, /run, /tmp excluded) is newer than a marker written before them" { check_only_home c; }
@test "SC-6 [bash -lc, notty] A bare Python package install and a global Node package install each succeed as the agent's user without privilege and persist across new shells — only the agent's home changed: after both installs nothing outside /home/agent (/proc, /sys, /dev, /run, /tmp excluded) is newer than a marker written before them" { check_only_home lc; }

# --- timelike's interpreter is unchanged ----------------------------------------------------------------
# SC6_TL_LIST — writes the sorted recursive listing of timelike's purelib to SC6_LIST_TO.
read -r -d '' SC6_TL_LIST <<'EOF' || true
p="$(/opt/timelike/python/bin/python3 -I -c 'import sysconfig; print(sysconfig.get_path("purelib"))')"
printf "purelib=%s\n" "$p"
if [ -d "$p" ]; then printf "purelib_dir=present\n"; else printf "purelib_dir=absent\n"; fi
find "$p" -printf "%P\t%s\t%T@\n" 2>&1 | LC_ALL=C sort >"$SC6_LIST_TO"
printf "entries=%s\n" "$(wc -l <"$SC6_LIST_TO")"
if [ -n "${SC6_LIST_BEFORE:-}" ]; then
  diff "$SC6_LIST_BEFORE" "$SC6_LIST_TO" | head -n 40 | sed "s/^/diff=/"
  cd / || exit 3
  /opt/timelike/python/bin/python3 -I -c "import ${SC6_MOD}" >/dev/null 2>&1
  printf "timelike_import_rc=%s\n" "$?"
  python3 -c "import ${SC6_MOD}" >/dev/null 2>&1
  printf "agent_import_rc=%s\n" "$?"
fi
printf "read=done\n"
EOF

check_timelike_untouched() {
  sc6_names
  sc6_dir
  run_in -e "SC6_LIST_TO=${SC6_D}/before" "$1" notty "$SC6_TL_LIST"
  assert_status 0
  assert_value read "done"
  assert_value purelib_dir present
  assert_matches entries '^[1-9][0-9]*$'
  local purelib
  purelib="$(value_of purelib)"

  sc6_install_python "$1"

  run_in -e "SC6_LIST_TO=${SC6_D}/after" -e "SC6_LIST_BEFORE=${SC6_D}/before" -e "SC6_MOD=${SC6_MOD}" \
    "$1" notty "$SC6_TL_LIST"
  assert_status 0
  assert_value read "done"
  assert_value purelib "$purelib"
  if [[ "$output" == *$'\n'diff=* || "$output" == diff=* ]]; then
    printf "timelike's purelib %s changed across a bare pip install:\n" "$purelib" >&2
    printf '%s\n' "${lines[@]}" | grep '^diff=' >&2
    return 1
  fi
  assert_value agent_import_rc 0
  if [[ "$(value_of timelike_import_rc)" == 0 ]]; then
    printf '/opt/timelike/python/bin/python3 -I imports %s, which the agent installed; output:\n%s\n' "$SC6_MOD" "$output" >&2
    return 1
  fi
}

@test "SC-6 [bash -c, notty] A bare Python package install and a global Node package install each succeed as the agent's user without privilege and persist across new shells — timelike's interpreter is unchanged: its purelib listing is equal before and after a bare pip install, and python3 -I cannot import the installed module" { check_timelike_untouched c; }
@test "SC-6 [bash -lc, notty] A bare Python package install and a global Node package install each succeed as the agent's user without privilege and persist across new shells — timelike's interpreter is unchanged: its purelib listing is equal before and after a bare pip install, and python3 -I cannot import the installed module" { check_timelike_untouched lc; }

# --- no PIP_BREAK_SYSTEM_PACKAGES -----------------------------------------------------------------------
# The pattern matches the variable and pip's configuration key alike (break-system-packages).
read -r -d '' SC6_NO_BREAK <<'EOF' || true
printf "env_set=%s\n" "${PIP_BREAK_SYSTEM_PACKAGES+set}"
printf "env_printenv=%s\n" "$(printenv PIP_BREAK_SYSTEM_PACKAGES)"
printf "env_any=%s\n" "$(env | grep -ic "break.system.packages")"
t="$(mktemp)"
pip config list >"$t" 2>&1
printf "pip_config_rc=%s\n" "$?"
printf "pip_config_break=%s\n" "$(grep -ic "break.system.packages" "$t")"
rm -f "$t"
for f in /opt/agent/python/pip.conf /opt/agent/node/etc/npmrc; do
  if [ -f "$f" ]; then printf "exists=%s\n" "$f"; fi
done
grep -rlis "break.system.packages" /etc /opt/agent/python/pip.conf /opt/agent/node/etc/npmrc \
  /etc/timelike /etc/profile.d | sed "s/^/found=/"
printf "read=done\n"
EOF

check_no_break() {
  run_in "$1" notty "$SC6_NO_BREAK"
  assert_status 0
  assert_value read "done"
  assert_value env_set ""
  assert_value env_printenv ""
  assert_value env_any 0
  assert_value pip_config_rc 0
  assert_value pip_config_break 0
  assert_output_has "exists=/opt/agent/python/pip.conf"
  assert_output_has "exists=/opt/agent/node/etc/npmrc"
  assert_no_line_matching '^found='
}

@test "SC-6 [bash -c, notty] A bare Python package install and a global Node package install each succeed as the agent's user without privilege and persist across new shells — no PIP_BREAK_SYSTEM_PACKAGES: not in the environment, not in pip config list, not in /etc, the agent pip.conf or the npmrc" { check_no_break c; }
@test "SC-6 [bash -lc, notty] A bare Python package install and a global Node package install each succeed as the agent's user without privilege and persist across new shells — no PIP_BREAK_SYSTEM_PACKAGES: not in the environment, not in pip config list, not in /etc, the agent pip.conf or the npmrc" { check_no_break lc; }

# --- the runtimes ------------------------------------------------------------------------------------
read -r -d '' SC6_RUNTIMES <<'EOF' || true
printf "agent_python=%s\n" "$(readlink -f /opt/agent/python)"
printf "agent_node=%s\n" "$(readlink -f /opt/agent/node)"
printf "timelike_python=%s\n" "$(readlink -f /opt/timelike/python)"
for n in python3 python pip pip3 node npm npx; do
  p="$(command -v "$n")"
  printf "path.%s=%s\n" "$n" "$p"
  if [ -L "$p" ]; then printf "link.%s=yes\n" "$n"; else printf "link.%s=no\n" "$n"; fi
  printf "real.%s=%s\n" "$n" "$(readlink -f "$p")"
done
printf "sys_prefix=%s\n" "$(python3 -c 'import os, sys; print(os.path.realpath(sys.prefix))' 2>&1)"
printf "python_version=%s\n" "$(python3 --version 2>&1)"
printf "node_version=%s\n" "$(node --version 2>&1)"
for d in /opt/agent/python/lib/python3.*/; do
  if [ -d "$d" ]; then printf "libdir=%s\n" "$d"; fi
  if [ -e "${d}EXTERNALLY-MANAGED" ]; then printf "marker=%sEXTERNALLY-MANAGED\n" "$d"; fi
done
printf "read=done\n"
EOF

check_runtimes() {
  local py_pin node_pin
  py_pin="$(pin_value PYTHON_VERSION)"
  node_pin="$(pin_value NODE_VERSION)"
  run_in "$1" notty "$SC6_RUNTIMES"
  assert_status 0
  assert_value read "done"
  local ap an tp n real prefix
  ap="$(value_of agent_python)"
  an="$(value_of agent_node)"
  tp="$(value_of timelike_python)"
  [[ "$ap" == /opt/agent/?* && "$an" == /opt/agent/?* ]] || {
    printf '/opt/agent/python (%q) or /opt/agent/node (%q) is not a directory under /opt/agent; output:\n%s\n' "$ap" "$an" "$output" >&2
    return 1
  }
  [[ -n "$tp" && "$ap" != "$tp" ]] || {
    printf "the agent prefix %q is timelike's interpreter %q; output:\n%s\n" "$ap" "$tp" "$output" >&2
    return 1
  }
  for n in python3 python pip pip3 node npm npx; do
    assert_value "path.${n}" "/usr/local/bin/${n}"
    assert_value "link.${n}" yes
    real="$(value_of "real.${n}")"
    case "$n" in
      node | npm | npx) prefix="$an" ;;
      *) prefix="$ap" ;;
    esac
    if [[ "$real" != "$prefix"/* || "$real" != /opt/agent/* || "$real" == /opt/timelike/* || "$real" == "$tp"/* ]]; then
      printf '%s resolves to %q: want inside %q (under /opt/agent/), never /opt/timelike or %q; output:\n%s\n' \
        "$n" "$real" "$prefix" "$tp" "$output" >&2
      return 1
    fi
  done
  assert_value sys_prefix "$ap"
  assert_value python_version "Python ${py_pin}"
  assert_value node_version "v${node_pin}"
  # The glob matched a library directory, so the marker's absence is not vacuous.
  assert_output_has "libdir=/opt/agent/python/lib/python3."
  assert_no_line_matching '^marker='
}

@test "SC-6 [bash -c, notty] A bare Python package install and a global Node package install each succeed as the agent's user without privilege and persist across new shells — the runtimes: python3, python, pip, pip3, node, npm and npx are /usr/local/bin links into /opt/agent at the pinned versions, never /opt/timelike; no EXTERNALLY-MANAGED marker" { check_runtimes c; }
@test "SC-6 [bash -lc, notty] A bare Python package install and a global Node package install each succeed as the agent's user without privilege and persist across new shells — the runtimes: python3, python, pip, pip3, node, npm and npx are /usr/local/bin links into /opt/agent at the pinned versions, never /opt/timelike; no EXTERNALLY-MANAGED marker" { check_runtimes lc; }
