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
# P6 (FR-13): the VANILLA bench image is untouched. It is started the way the bench starts it (its own
# entrypoint, i.e. none; `docker run --rm`), and must hold none of the three user-level files in its
# home, no /etc/timelike/announcement.md and no timelike entrypoint, and declare no ENTRYPOINT. The tag is
# speedup-bench.bats' `timelike-vanilla:local` (built by tests/run.sh's benchimg step); its revision label
# must be HEAD, so a stale vanilla image fails rather than passes vacuously. Its user and home are read
# back and must be `agent` and /home/agent, which bench/vanilla/Dockerfile § 2 and § 4 declare, so the
# home checked is the home the agent image's placement targets.
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
READ_VANILLA='printf "user=%s\n" "$(id -un)"
printf "home=%s\n" "$HOME"
printf "passwd_home=%s\n" "$(getent passwd "$(id -u)" | cut -d: -f6)"
for f in "$HOME/.claude/CLAUDE.md" "${CODEX_HOME:-$HOME/.codex}/AGENTS.md" "$HOME/.config/opencode/AGENTS.md" \
  "$HOME/CLAUDE.md" "$HOME/AGENTS.md" /etc/timelike/announcement.md /etc/timelike/standard-tools.json \
  /opt/timelike/libexec/entrypoint; do
  if [ -e "$f" ]; then printf "present=%s\n" "$f"; fi
done
printf "read=done\n"'

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
    printf '%s declares an ENTRYPOINT (%s): FR-13 says the vanilla image is unchanged\n' "$VANILLA_IMAGE" "$entry" >&2
    return 1
  fi
  local -a shell
  mapfile -t shell < <(_shell_argv "$1")
  run timeout "$RUN_TIMEOUT" docker run --rm --network none --cap-drop ALL \
    --security-opt no-new-privileges:true --label "${THROWAWAY_LABEL}=1" \
    "$VANILLA_IMAGE" "${shell[@]}" "$READ_VANILLA"
  assert_status 0
  assert_value read "done"
  assert_value user agent
  assert_value home /home/agent
  assert_value passwd_home /home/agent
  assert_no_line_matching '^present='
}

@test "SC-3 [bash -c, notty] One command prints a manifest of every timelike tool and curated standard tools with fields for JSON support, interactivity risk and safer alternative — timelike tools --json: every installed tool and every curated entry, each with json, interactive_risk and instead in the contract's vocabulary" { check_manifest_json c notty; }
@test "SC-3 [bash -lc, notty] One command prints a manifest of every timelike tool and curated standard tools with fields for JSON support, interactivity risk and safer alternative — timelike tools --json: every installed tool and every curated entry, each with json, interactive_risk and instead in the contract's vocabulary" { check_manifest_json lc notty; }
@test "SC-3 [bash -c, notty] One command prints a manifest of every timelike tool and curated standard tools with fields for JSON support, interactivity risk and safer alternative — timelike tools --text: one line per entry, timelike first, then by name" { check_manifest_text c notty; }
@test "SC-3 [bash -lc, notty] One command prints a manifest of every timelike tool and curated standard tools with fields for JSON support, interactivity risk and safer alternative — timelike tools --text: one line per entry, timelike first, then by name" { check_manifest_text lc notty; }
@test "P6 [bash -c] the vanilla bench image is untouched: no announcement in its home, none in /etc/timelike, no entrypoint" { check_vanilla_untouched c; }
@test "P6 [bash -lc] the vanilla bench image is untouched: no announcement in its home, none in /etc/timelike, no entrypoint" { check_vanilla_untouched lc; }
