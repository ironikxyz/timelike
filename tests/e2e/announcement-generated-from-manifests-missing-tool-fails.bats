#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# Feature 007 (prompt 04, slice 0), SC-2 (tasks.md T003; spec FR-1 to FR-4, D-6; contract § The
# announcement):
#   SC-2 "The announcement is generated from the installed tools' manifests, and a test fails if any
#        installed timelike tool is missing from it"
#
# In the running agent container, from outside (lore cross-stack P005). Every expected value is computed
# by this test in the container, never written here (cross-stack P004):
#   - the installed tools: the executables in /opt/timelike/bin, listed directly;
#   - each tool's summary: its own `NAME --agent-info`, run by path and read with the image's Python;
#   - the revision: /opt/timelike/REVISION (stamp_check has already tied it to HEAD and the label).
#
# Checks:
#   1. /etc/timelike/announcement.md: line 1 is the contract's marker carrying the revision; at most 60
#      lines; its `## Tools` section lists, as "- `NAME` — SUMMARY", exactly the installed tools, in name
#      order, each with the summary its own --agent-info gives. THIS is "a test fails if any installed
#      timelike tool is missing from it": a tool in the bin directory but not in the file fails here.
#   2. Generated, not maintained: `timelike announce --json`, run now, gives the file's lines (contract:
#      "--json gives the same lines"). ASSUMED: the JSON's `lines` are the announcement's lines, one per
#      element, with no rule-13 cut (every announcement line is well under COLUMNS=200).
#   3. `timelike announce --check` exits 0 on the image's file, and 0 on an unmodified copy (control:
#      the path argument is honoured and the copy itself is valid).
#   4. A copy with one installed tool's line removed (the middle tool of the sorted list, chosen by the
#      test from what is installed) makes `--check <copy>` exit 1 with `missing: NAME` in the JSON
#      verdict, NAME bounded so that `timelike` cannot match `timelike-conform`. The path follows
#      --check directly: `--check [P]` takes an optional value.
#
# Cells: bash -c and bash -lc in `notty`; the commands under test are `timelike announce ...`.

load helpers

setup_file() {
  stamp_check
  SC2_DIR="$(container_tmpdir sc2)"
  export SC2_DIR
}

teardown_file() {
  container_rm "${SC2_DIR:-}"
}

# READ_EXPECTED — run in the container under the style under test. Prints KEY=value lines:
#   revision, marker, lines, bin (comma list, sorted), listed (comma list, file order), malformed,
#   summary.NAME (from --agent-info), announced.NAME (from the file), regenerated (equal | why not).
read -r -d '' READ_EXPECTED <<'EOF' || true
gen="$(mktemp)"
timelike announce --json >"$gen" 2>/dev/null
printf "announce_rc=%s\n" "$?"
/opt/timelike/python/bin/python3 -I -c '
import json, os, re, subprocess, sys
BIN = "/opt/timelike/bin"
ANN = "/etc/timelike/announcement.md"
rev = open("/opt/timelike/REVISION", encoding="utf-8").read().strip()
print("revision=%s" % rev)
try:
    text = open(ANN, encoding="utf-8").read()
except OSError as exc:
    print("marker=<unreadable: %s>" % exc)
    raise SystemExit(0)
lines = text.split("\n")
if lines and lines[-1] == "":
    lines.pop()
print("marker=%s" % (lines[0] if lines else "<empty>"))
print("lines=%d" % len(lines))
tools = sorted(e.name for e in os.scandir(BIN) if e.is_file() and os.access(e.path, os.X_OK))
print("bin=%s" % ",".join(tools))
listed, malformed, announced, section = [], [], {}, False
pat = re.compile("^- `([^`]+)` — (.*)$")
for line in lines:
    if line.startswith("## "):
        section = line.strip() == "## Tools"
        continue
    if not section or not line.strip():
        continue
    m = pat.match(line)
    if m:
        listed.append(m.group(1))
        announced[m.group(1)] = m.group(2)
    else:
        malformed.append(line)
print("listed=%s" % ",".join(listed))
print("malformed=%s" % " | ".join(malformed))
for t in tools:
    try:
        out = subprocess.run([os.path.join(BIN, t), "--agent-info"], capture_output=True, text=True,
                             timeout=15, stdin=subprocess.DEVNULL).stdout
        summary = json.loads(out).get("summary")
    except Exception as exc:
        summary = "<agent-info failed: %s>" % type(exc).__name__
    print("summary.%s=%s" % (t, summary))
    print("announced.%s=%s" % (t, announced.get(t, "<absent>")))
try:
    gen = json.load(open(sys.argv[1], encoding="utf-8")).get("lines")
except (OSError, ValueError, AttributeError) as exc:
    gen = None
if gen == lines:
    print("regenerated=equal")
elif not isinstance(gen, list):
    print("regenerated=<no lines in timelike announce --json>")
else:
    diff = next((i for i, (a, b) in enumerate(zip(gen, lines)) if a != b), min(len(gen), len(lines)))
    print("regenerated=differs at line %d (%d generated, %d in the file)" % (diff + 1, len(gen), len(lines)))
' "$gen"
rm -f "$gen"
printf "read=done\n"
EOF

# drop_tool_line SRC DEST NAME — copy SRC to DEST without NAME's line in `## Tools`; prints the count
# of lines removed. Setup, not under test: exec_plain, the image's Python.
drop_tool_line() {
  exec_plain "$AGENT_PY" -I -c '
import sys
src, dst, name = sys.argv[1:4]
removed, section, out = 0, False, []
for line in open(src, encoding="utf-8").read().split("\n"):
    if line.startswith("## "):
        section = line.strip() == "## Tools"
    if section and line.startswith("- `%s` " % name):
        removed += 1
        continue
    out.append(line)
open(dst, "w", encoding="utf-8").write("\n".join(out))
print(removed)
' "$1" "$2" "$3"
}

# json_verdict — the "verdict" of the last run's JSON (the default when piped; agentio prints it with
# json.dumps' default separators), or nothing.
json_verdict() {
  local re='"verdict": "([^"\\]*)"'
  if [[ "$output" =~ $re ]]; then
    printf '%s' "${BASH_REMATCH[1]}"
  fi
}

check_generated_from_manifests() {
  run_in "$1" "$2" "$READ_EXPECTED"
  assert_within 20
  assert_status 0
  assert_value read "done"
  assert_value announce_rc 0
  local rev n bin listed t
  rev="$(value_of revision)"
  [[ -n "$rev" && "$rev" == "$GIT_SHA" ]] || {
    printf '/opt/timelike/REVISION %q is not HEAD %q\n' "$rev" "$GIT_SHA" >&2
    return 1
  }
  assert_value marker "<!-- timelike announcement: revision ${rev}; generated from the tools' manifests; do not edit -->"
  n="$(value_of lines)"
  if ! [[ "$n" =~ ^[0-9]+$ ]] || ((n < 1 || n > 60)); then
    printf 'the announcement has %q lines; the bound is 60\n' "$n" >&2
    return 1
  fi
  bin="$(value_of bin)"
  listed="$(value_of listed)"
  [[ -n "$bin" ]] || {
    printf 'no executable found in /opt/timelike/bin; output:\n%s\n' "$output" >&2
    return 1
  }
  for t in ${bin//,/ }; do
    if [[ "$(value_of "announced.$t")" == "<absent>" ]]; then
      printf 'installed tool %s is MISSING from the announcement (## Tools lists: %s); output:\n%s\n' "$t" "$listed" "$output" >&2
      return 1
    fi
    if [[ "$(value_of "summary.$t")" == "<agent-info failed"* ]]; then
      printf '%s --agent-info failed in the image: %s\n' "$t" "$(value_of "summary.$t")" >&2
      return 1
    fi
    if [[ "$(value_of "announced.$t")" != "$(value_of "summary.$t")" ]]; then
      printf '%s: announced %q, but its --agent-info summary is %q\n' "$t" "$(value_of "announced.$t")" "$(value_of "summary.$t")" >&2
      return 1
    fi
  done
  # Exactly the installed tools, in name order: no extra, no duplicate.
  if [[ "$listed" != "$bin" ]]; then
    printf '## Tools lists %q; installed, in name order: %q\n' "$listed" "$bin" >&2
    return 1
  fi
  assert_value malformed ""
  assert_value regenerated equal
}

check_check_passes() {
  # One copy per cell. cp gives the copy the source's 0444, so a second cell's cp into the same
  # name fails as agent (Permission denied): the lane batch-a failure of the -lc cell.
  local copy="${SC2_DIR}/copy-$1-$2.md"
  exec_plain cp /etc/timelike/announcement.md "$copy"
  run_in "$1" "$2" "timelike announce --check"
  assert_within 20
  assert_status 0
  run_in "$1" "$2" "timelike announce --check '$copy'"
  assert_within 20
  assert_status 0
}

check_missing_tool_fails() {
  local bin name removed verdict
  local -a tools
  bin="$(exec_plain "$AGENT_PY" -I -c '
import os
d = "/opt/timelike/bin"
print(",".join(sorted(e.name for e in os.scandir(d) if e.is_file() and os.access(e.path, os.X_OK))))
')"
  IFS=, read -r -a tools <<<"$bin"
  [[ ${#tools[@]} -gt 0 ]] || { echo "no executable in /opt/timelike/bin" >&2; return 1; }
  name="${tools[${#tools[@]} / 2]}"
  removed="$(drop_tool_line /etc/timelike/announcement.md "${SC2_DIR}/without-${name}.md" "$name")"
  if [[ "$removed" != 1 ]]; then
    printf 'expected to remove exactly one "- `%s` " line from ## Tools, removed %q\n' "$name" "$removed" >&2
    return 1
  fi
  run_in "$1" "$2" "timelike announce --check '${SC2_DIR}/without-${name}.md'"
  assert_within 20
  assert_status 1
  verdict="$(json_verdict)"
  if ! [[ "$verdict" =~ (^|[^[:alnum:]_.-])missing:\ ([^;]*[ ,])?${name}($|[^[:alnum:]_.-]) ]]; then
    printf 'the verdict does not name %s as missing: %q; output:\n%s\n' "$name" "$verdict" "$output" >&2
    return 1
  fi
}

@test "SC-2 [bash -c, notty] The announcement is generated from the installed tools' manifests, and a test fails if any installed timelike tool is missing from it — every executable in /opt/timelike/bin is listed with its own --agent-info summary, under the revision marker, at most 60 lines" { check_generated_from_manifests c notty; }
@test "SC-2 [bash -lc, notty] The announcement is generated from the installed tools' manifests, and a test fails if any installed timelike tool is missing from it — every executable in /opt/timelike/bin is listed with its own --agent-info summary, under the revision marker, at most 60 lines" { check_generated_from_manifests lc notty; }
@test "SC-2 [bash -c, notty] The announcement is generated from the installed tools' manifests, and a test fails if any installed timelike tool is missing from it — timelike announce --check exits 0 on the image's announcement and on an unmodified copy" { check_check_passes c notty; }
@test "SC-2 [bash -lc, notty] The announcement is generated from the installed tools' manifests, and a test fails if any installed timelike tool is missing from it — timelike announce --check exits 0 on the image's announcement and on an unmodified copy" { check_check_passes lc notty; }
@test "SC-2 [bash -c, notty] The announcement is generated from the installed tools' manifests, and a test fails if any installed timelike tool is missing from it — a copy missing one installed tool's line makes --check exit 1 naming it" { check_missing_tool_fails c notty; }
@test "SC-2 [bash -lc, notty] The announcement is generated from the installed tools' manifests, and a test fails if any installed timelike tool is missing from it — a copy missing one installed tool's line makes --check exit 1 naming it" { check_missing_tool_fails lc notty; }
