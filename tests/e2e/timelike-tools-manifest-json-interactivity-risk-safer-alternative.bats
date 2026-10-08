#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# Feature 007 (prompt 04, slice 0), SC-3 (tasks.md T003; spec FR-9 to FR-12; contract § The manifest),
# and P6 (spec FR-13, D-5; send seam 2):
#   SC-3 "One command prints a manifest of every timelike tool and curated standard tools with fields
#        for JSON support, interactivity risk and safer alternative"
#
# In the running agent container, from outside (lore cross-stack P005). Expected values are computed by
# this test in the container (cross-stack P004): the timelike tools are the executables in
# /opt/timelike/bin, listed directly; their summaries come from each tool's own --agent-info; the curated
# entries are read from the file the image ships, /etc/timelike/standard-tools.json
# (or $TIMELIKE_STANDARD_TOOLS where the shell under test sets it, which is the file the command reads).
#
#   1. `timelike tools --json`: exit 0; `tools` holds one `kind: timelike` entry per installed tool
#      (same names, `installed: true`, summary equal to its --agent-info summary) and one `kind:
#      standard` entry per curated entry (same name, summary, json, interactive_risk and instead as the
#      file); every entry has every field of the contract with the contract's vocabulary:
#        json              yes | no | "partial: <how>"
#        interactive_risk  none | a comma list of pager, editor, prompt, repl, waits, unbounded output
#        instead           a string (a command, or "")
#        installed         a boolean
#      and the verdict reads "N timelike tools, M standard tools (K installed)" with N and M as counted.
#   2. `timelike tools --text`: exactly one line per entry, starting "NAME  [KIND]  json=…  risk=…"
#      (contract § The manifest, two spaces between fields), timelike entries first, then by name
#      (FR-12). ASSUMED: "by name" is Python's default string order within each kind.
#
# P6 (FR-13, revised at discovery revision 14): the VANILLA bench image has the same agent runtimes, with
# stock behaviour, and nothing of timelike. It is started the way the bench starts it (its own entrypoint,
# i.e. none; `docker run --rm`, here with no network), as its own user, which must be `agent` with home
# /home/agent (bench/vanilla/Dockerfile § 2 and § 4), so the home checked is the home the agent image's
# placement targets. The tag is speedup-bench.bats' `timelike-vanilla:local` (built by tests/run.sh's
# benchimg step); its revision label must be HEAD, so a stale vanilla image fails rather than passes
# vacuously. It must:
#   - declare no ENTRYPOINT, and hold none of the three user-level files in its home, no /etc/timelike
#     (so no announcement and no missing-commands data) and no timelike entrypoint;
#   - report the same `python3 --version` and `node --version` as the running agent container, read under
#     the same style (the runtimes come from the same pins, FR-30);
#   - keep the agent interpreter's lib/python3.*/EXTERNALLY-MANAGED marker, and have neither
#     /opt/agent/python/pip.conf nor /opt/agent/node/etc/npmrc;
#   - answer `npm prefix -g` with /opt/agent/node, npm's default for that Node;
#   - refuse a bare `pip install --no-index` of a wheel the cell builds there (stdlib zipfile, a name and
#     version unique to the cell): non-zero, pip's externally-managed-environment error, and the module
#     still not importable afterwards. The wheel is built first and must exist, so the refusal is pip's
#     and not a missing file's;
#   - have no `.local/bin` entry and no /opt/timelike entry on PATH.
#
# Cells: bash -c and bash -lc in `notty`.

load helpers

VANILLA_IMAGE=timelike-vanilla:local

setup_file() {
  stamp_check
}

# READ_MANIFEST — under the style under test. Runs `timelike tools --json` and prints KEY=value lines;
# `problem=` lines name every entry that breaks the contract; `entry=KIND|NAME|JSON|RISK` lines give the
# expected text-mode order (timelike first, then by name).
read -r -d '' READ_MANIFEST <<'EOF' || true
out="$(mktemp)"
timelike tools --json >"$out" 2>"$out.err"
printf "tools_rc=%s\n" "$?"
printf "tools_err=%s\n" "$(head -c 300 "$out.err" | tr "\n" " ")"
/opt/timelike/python/bin/python3 -I -c '
import json, os, subprocess, sys
BIN = "/opt/timelike/bin"
CURATED = os.environ.get("TIMELIKE_STANDARD_TOOLS") or "/etc/timelike/standard-tools.json"
RISKS = {"pager", "editor", "prompt", "repl", "waits", "unbounded output"}
FIELDS = ("name", "kind", "installed", "summary", "json", "interactive_risk", "instead")
problems = []
installed = sorted(e.name for e in os.scandir(BIN) if e.is_file() and os.access(e.path, os.X_OK))
print("bin=%s" % ",".join(installed))
summaries = {}
for t in installed:
    try:
        r = subprocess.run([os.path.join(BIN, t), "--agent-info"], capture_output=True, text=True,
                           timeout=15, stdin=subprocess.DEVNULL)
        summaries[t] = json.loads(r.stdout).get("summary")
    except Exception as exc:
        problems.append("%s --agent-info failed: %s" % (t, type(exc).__name__))
try:
    curated = json.load(open(CURATED, encoding="utf-8"))["tools"]
    want_standard = sorted(tuple(str(c[k]) for k in ("name", "summary", "json", "interactive_risk", "instead")) for c in curated)
except Exception as exc:
    print("curated=<unreadable %s: %s>" % (CURATED, exc))
    raise SystemExit(0)
print("curated=%d" % len(curated))
try:
    doc = json.load(open(sys.argv[1], encoding="utf-8"))
except (OSError, ValueError) as exc:
    print("tools_json=invalid: %s" % exc)
    raise SystemExit(0)
print("tools_json=ok")
print("verdict=%s" % doc.get("verdict"))
entries = doc.get("tools")
if not isinstance(entries, list):
    print("entries=<absent>")
    raise SystemExit(0)
print("entries=%d" % len(entries))
def risk_ok(v):
    if v == "none":
        return True
    items = [x.strip() for x in v.split(",")]
    return bool(items) and all(x in RISKS for x in items)
got_timelike, got_standard, order = [], [], []
for i, e in enumerate(entries):
    if not isinstance(e, dict):
        problems.append("entry %d is not an object" % i)
        continue
    name = e.get("name")
    missing = [f for f in FIELDS if f not in e]
    if missing:
        problems.append("%s lacks %s" % (name, ",".join(missing)))
        continue
    if not isinstance(name, str) or not name:
        problems.append("entry %d has no name" % i)
        continue
    for f in ("summary", "json", "interactive_risk", "instead"):
        if not isinstance(e[f], str):
            problems.append("%s: %s is not a string" % (name, f))
    if not isinstance(e["installed"], bool):
        problems.append("%s: installed is not a boolean" % name)
    j, r = e["json"], e["interactive_risk"]
    if isinstance(j, str) and not (j in ("yes", "no") or (j.startswith("partial: ") and j[9:].strip())):
        problems.append("%s: json %r is outside yes | no | partial: <how>" % (name, j))
    if isinstance(r, str) and not risk_ok(r):
        problems.append("%s: interactive_risk %r is outside the vocabulary" % (name, r))
    if e["kind"] == "timelike":
        got_timelike.append(name)
        if e["installed"] is not True:
            problems.append("%s: a timelike tool not installed" % name)
        if name in summaries and e["summary"] != summaries[name]:
            problems.append("%s: summary %r, --agent-info says %r" % (name, e["summary"], summaries[name]))
    elif e["kind"] == "standard":
        got_standard.append(tuple(str(x) for x in (name, e["summary"], j, r, e["instead"])))
    else:
        problems.append("%s: kind %r" % (name, e["kind"]))
        continue
    order.append((e["kind"] != "timelike", name, str(e["kind"]), str(j), str(r)))
print("timelike=%s" % ",".join(sorted(got_timelike)))
print("timelike_count=%d" % len(got_timelike))
print("standard_count=%d" % len(got_standard))
if sorted(got_standard) != want_standard:
    extra = sorted(set(got_standard) - set(want_standard))
    lacking = sorted(set(want_standard) - set(got_standard))
    problems.append("standard entries differ from %s: not in the file %r; in the file but not listed %r" % (CURATED, extra, lacking))
for p in problems:
    print("problem=%s" % p)
for _, name, kind, j, r in sorted(order):
    print("entry=%s|%s|%s|%s" % (kind, name, j, r))
' "$out"
rm -f "$out" "$out.err"
printf "read=done\n"
EOF

check_manifest_json() {
  run_in "$1" "$2" "$READ_MANIFEST"
  assert_within 20
  assert_status 0
  assert_value read "done"
  assert_value tools_rc 0
  assert_value tools_json ok
  local bin curated n m line
  bin="$(value_of bin)"
  curated="$(value_of curated)"
  [[ -n "$bin" ]] || {
    printf 'no executable found in /opt/timelike/bin; output:\n%s\n' "$output" >&2
    return 1
  }
  [[ "$curated" =~ ^[0-9]+$ && "$curated" -gt 0 ]] || {
    printf 'the curated file is unreadable or empty (curated=%s); output:\n%s\n' "$curated" "$output" >&2
    return 1
  }
  for line in "${lines[@]}"; do
    if [[ "$line" == problem=* ]]; then
      printf 'manifest problems:\n' >&2
      printf '%s\n' "${lines[@]}" | grep '^problem=' >&2
      return 1
    fi
  done
  # Every installed tool, and nothing else, as kind timelike.
  assert_value timelike "$bin"
  n="$(value_of timelike_count)"
  m="$(value_of standard_count)"
  assert_value standard_count "$curated"
  assert_value entries "$((n + m))"
  local verdict re
  verdict="$(value_of verdict)"
  re="^${n} timelike tools, ${m} standard tools \\([0-9]+ installed\\)$"
  if ! [[ "$verdict" =~ $re ]]; then
    printf 'verdict %q; expected "%s timelike tools, %s standard tools (K installed)"\n' "$verdict" "$n" "$m" >&2
    return 1
  fi
}

check_manifest_text() {
  run_in "$1" "$2" "$READ_MANIFEST"
  assert_within 20
  assert_status 0
  assert_value read "done"
  local -a expected=()
  local line
  for line in "${lines[@]}"; do
    [[ "$line" == entry=* ]] && expected+=("${line#entry=}")
  done
  [[ ${#expected[@]} -gt 0 ]] || {
    printf 'no manifest entries to look for; output:\n%s\n' "$output" >&2
    return 1
  }

  run_in "$1" "$2" "timelike tools --text"
  assert_within 20
  assert_status 0
  local e kind name json risk prefix i found at last=-1
  for e in "${expected[@]}"; do
    IFS='|' read -r kind name json risk <<<"$e"
    prefix="${name}  [${kind}]  json=${json}  risk=${risk}"
    found=0
    for i in "${!lines[@]}"; do
      if [[ "${lines[$i]}" == "$prefix"* ]]; then
        found=$((found + 1))
        at=$i
      fi
    done
    if [[ "$found" != 1 ]]; then
      printf 'expected exactly one line starting %q, found %s; output:\n%s\n' "$prefix" "$found" "$output" >&2
      return 1
    fi
    if ((at <= last)); then
      printf 'out of order (timelike first, then by name): %q comes before an entry that sorts ahead of it; output:\n%s\n' \
        "$prefix" "$output" >&2
      return 1
    fi
    last=$at
  done
}

# --- P6: the vanilla image ------------------------------------------------------------------------
# READ_VANILLA — in the vanilla image, under the style under test. Inputs (-e): P6_MOD, P6_VER, the
# wheel's module name and version, unique to the cell.
read -r -d '' READ_VANILLA <<'EOF' || true
printf "user=%s\n" "$(id -un)"
printf "home=%s\n" "$HOME"
printf "passwd_home=%s\n" "$(getent passwd "$(id -u)" | cut -d: -f6)"
for f in "$HOME/.claude/CLAUDE.md" "${CODEX_HOME:-$HOME/.codex}/AGENTS.md" "$HOME/.config/opencode/AGENTS.md" \
  "$HOME/CLAUDE.md" "$HOME/AGENTS.md" /etc/timelike /etc/timelike/announcement.md /etc/timelike/standard-tools.json \
  /etc/timelike/missing-commands.tsv /opt/timelike/libexec/entrypoint /opt/agent/python/pip.conf /opt/agent/node/etc/npmrc; do
  if [ -e "$f" ]; then printf "present=%s\n" "$f"; fi
done
printf "python_version=%s\n" "$(python3 --version 2>&1)"
printf "node_version=%s\n" "$(node --version 2>&1)"
for d in /opt/agent/python/lib/python3.*/; do
  if [ -e "${d}EXTERNALLY-MANAGED" ]; then printf "marker=%sEXTERNALLY-MANAGED\n" "$d"; fi
done
printf "npm_prefix_g=%s\n" "$(npm prefix -g 2>/dev/null | tr "\n" " " | sed "s/ *$//")"
printf "path=%s\n" "$PATH"
w="$(mktemp -d)"
whl="$(python3 -I -c '
import base64, hashlib, sys, zipfile
out, mod, ver = sys.argv[1:4]
di = "%s-%s.dist-info" % (mod, ver)
files = {
    mod + "/__init__.py": "",
    di + "/METADATA": "Metadata-Version: 2.1\nName: %s\nVersion: %s\n" % (mod, ver),
    di + "/WHEEL": "Wheel-Version: 1.0\nGenerator: timelike-e2e\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
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
' "$w" "$P6_MOD" "$P6_VER" 2>&1)"
printf "build_rc=%s\n" "$?"
if [ -f "$whl" ]; then printf "wheel=present\n"; else printf "wheel=absent %s\n" "$whl"; fi
pip install --no-index "$whl" >"$w/pip.out" 2>&1
printf "pip_rc=%s\n" "$?"
printf "pip_refused=%s\n" "$(grep -ic "externally-managed-environment" "$w/pip.out")"
printf "pip_out=%s\n" "$(tail -c 600 "$w/pip.out" | tr "\n" " ")"
cd / && python3 -c "import ${P6_MOD}" >/dev/null 2>&1
printf "import_after_rc=%s\n" "$?"
rm -rf "$w"
printf "read=done\n"
EOF

check_vanilla_untouched() {
  local label entry
  label="$(timeout "$RUN_TIMEOUT" docker image inspect --format "{{ index .Config.Labels \"${REVISION_LABEL}\" }}" "$VANILLA_IMAGE" </dev/null 2>&1)" || {
    printf 'cannot inspect %s (built by tests/run.sh step benchimg): %s\n' "$VANILLA_IMAGE" "$label" >&2
    return 1
  }
  if [[ "$label" != "$GIT_SHA" ]]; then
    printf 'stale vanilla image: %s carries revision %q, HEAD is %q (rebuild with make bench-images)\n' "$VANILLA_IMAGE" "$label" "$GIT_SHA" >&2
    return 1
  fi
  entry="$(timeout "$RUN_TIMEOUT" docker image inspect --format '{{json .Config.Entrypoint}}' "$VANILLA_IMAGE" </dev/null 2>&1)"
  if [[ "$entry" != null && "$entry" != "[]" ]]; then
    printf '%s declares an ENTRYPOINT (%s): FR-13 says the vanilla image declares none\n' "$VANILLA_IMAGE" "$entry" >&2
    return 1
  fi

  # The agent container's runtimes, under the same style: what the vanilla image must match.
  run_in "$1" notty 'printf "python_version=%s\n" "$(python3 --version 2>&1)"; printf "node_version=%s\n" "$(node --version 2>&1)"'
  assert_status 0
  local agent_py agent_node
  agent_py="$(value_of python_version)"
  agent_node="$(value_of node_version)"
  [[ "$agent_py" =~ ^Python\ 3\.[0-9]+\.[0-9]+$ && "$agent_node" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
    printf 'the agent container reports python3 %q and node %q: not versions; output:\n%s\n' "$agent_py" "$agent_node" "$output" >&2
    return 1
  }

  local n="$((RANDOM % 9 + 1))${RANDOM}${RANDOM}"
  local mod="tlprobe_${n}" ver="1.0.${n}"
  local -a shell
  mapfile -t shell < <(_shell_argv "$1")
  run timeout "$RUN_TIMEOUT" docker run --rm --network none --cap-drop ALL \
    --security-opt no-new-privileges:true --label "${THROWAWAY_LABEL}=1" \
    -e "P6_MOD=${mod}" -e "P6_VER=${ver}" \
    "$VANILLA_IMAGE" "${shell[@]}" "$READ_VANILLA"
  assert_status 0
  assert_value read "done"
  assert_value user agent
  assert_value home /home/agent
  assert_value passwd_home /home/agent
  assert_no_line_matching '^present='
  # The same runtimes (FR-13, FR-30) ...
  assert_value python_version "$agent_py"
  assert_value node_version "$agent_node"
  # ... with stock behaviour.
  assert_output_has "marker=/opt/agent/python/lib/python3."
  assert_value npm_prefix_g /opt/agent/node
  assert_value build_rc 0
  assert_value wheel present
  if [[ "$(value_of pip_rc)" == 0 || "$(value_of pip_refused)" == 0 ]]; then
    printf 'a bare pip install in %s was not refused as externally managed (rc %s); output:\n%s\n' \
      "$VANILLA_IMAGE" "$(value_of pip_rc)" "$output" >&2
    return 1
  fi
  if [[ "$(value_of import_after_rc)" == 0 ]]; then
    printf '%s imports %s after the refused install; output:\n%s\n' "$VANILLA_IMAGE" "$mod" "$output" >&2
    return 1
  fi
  # Nothing of timelike on PATH.
  local path entry_dir
  path="$(value_of path)"
  local -a dirs
  IFS=: read -r -a dirs <<<"$path"
  for entry_dir in "${dirs[@]}"; do
    if [[ "$entry_dir" == */.local/bin || "$entry_dir" == */.local/bin/ || "$entry_dir" == /opt/timelike* ]]; then
      printf '%s has %q on PATH (%s): FR-13 keeps it stock\n' "$VANILLA_IMAGE" "$entry_dir" "$path" >&2
      return 1
    fi
  done
}

@test "SC-3 [bash -c, notty] One command prints a manifest of every timelike tool and curated standard tools with fields for JSON support, interactivity risk and safer alternative — timelike tools --json: every installed tool and every curated entry, each with json, interactive_risk and instead in the contract's vocabulary" { check_manifest_json c notty; }
@test "SC-3 [bash -lc, notty] One command prints a manifest of every timelike tool and curated standard tools with fields for JSON support, interactivity risk and safer alternative — timelike tools --json: every installed tool and every curated entry, each with json, interactive_risk and instead in the contract's vocabulary" { check_manifest_json lc notty; }
@test "SC-3 [bash -c, notty] One command prints a manifest of every timelike tool and curated standard tools with fields for JSON support, interactivity risk and safer alternative — timelike tools --text: one line per entry, timelike first, then by name" { check_manifest_text c notty; }
@test "SC-3 [bash -lc, notty] One command prints a manifest of every timelike tool and curated standard tools with fields for JSON support, interactivity risk and safer alternative — timelike tools --text: one line per entry, timelike first, then by name" { check_manifest_text lc notty; }
@test "P6 [bash -c] the vanilla bench image has the same agent runtimes with stock behaviour and nothing of timelike — same python3 and node versions as the agent container, EXTERNALLY-MANAGED kept, no pip.conf or npmrc, npm prefix -g /opt/agent/node, a bare pip install refused, no .local/bin or /opt/timelike on PATH, no announcement, no /etc/timelike, no entrypoint" { check_vanilla_untouched c; }
@test "P6 [bash -lc] the vanilla bench image has the same agent runtimes with stock behaviour and nothing of timelike — same python3 and node versions as the agent container, EXTERNALLY-MANAGED kept, no pip.conf or npmrc, npm prefix -g /opt/agent/node, a bare pip install refused, no .local/bin or /opt/timelike on PATH, no announcement, no /etc/timelike, no entrypoint" { check_vanilla_untouched lc; }
