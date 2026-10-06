#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-2 — "A definition lookup returns the defining file and line first, exits 3 when the symbol is not
# found, and answers in under 2 seconds warm on a 1,000-file repository". (Feature 011, slice 1; spec
# FR-1, FR-2, FR-5, FR-9, Scenario 2; tasks.md T002; contracts/symbols-cli.md § def; research R1, R4, R7.)
#
# Written from the contract before the tool existed. Every expected value is the test's own (P005):
#   - the ranking fixture defines `persist` four times, one per rank of R4 / FR-5: a top-level Python
#     function (`lib/store.py:4`), a Python method (`app/orders.py:2`), a Python nested function
#     (`app/util.py:2`) and a JavaScript function (`web/persist.js:2`, text-based: its path naming the
#     name does not lift it over exact ones). A comment and a string carry `def persist(` text that is
#     not a definition. Four files, so four indexed;
#   - `symbols def persist --json`: `definitions` are exactly those four, in that order; the first
#     entry is `lib/store.py` line 4; the JavaScript one's precision says `text-based`, the others' do
#     not; the scope says `4 definitions` and `mixed`;
#   - `symbols def persist --text`: the first line after the verdict starts `lib/store.py:4`, and the
#     four body lines are the four `FILE:LINE`s in that order;
#   - `symbols def no_such_symbol_q7` (a name the fixture never uses): exit 3 under `--json` and
#     `--text`; the scope is `not found`; the verdict is `no definition of no_such_symbol_q7 in 4
#     indexed files`; the output or its stderr carries `search -w no_such_symbol_q7`;
#   - timing: a 1,000-file repository generated in the container by the image's python (GEN_PY: 20
#     packages of 50 modules, each 3 classes of 4 methods and 5 functions, R1's shape), with one
#     `needle_0500` planted at `pkg10/mod0500.py:3`. A cold `symbols def needle_0500 --json` says
#     `cache: built (1000 files)` and answers that location; then the warm call is timed INSIDE the
#     container around the command alone (bash EPOCHREALTIME), under 2 s, its verdict says
#     `cache: fresh`, and its first answer line is `pkg10/mod0500.py:3`. The runner's own bound (20 s)
#     only catches a hang.
#
# Fixtures are written by the container's printf and python (P005), never by `symbols`. Isolation: each
# cell has its own workspace (a directory holding `.git`) and its own TIMELIKE_SESSION
# (`sy2-<run id>-<check>-<style>`), checked to have no records before the cell starts. Output files sit
# beside the workspace, never in it, so they never change the index. teardown_file removes the
# workspaces and this run's session directories (by that prefix) and nothing else.
# Cells: bash -c and bash -lc, `notty`.

load helpers

# This file's session prefix (sessions are `<prefix>-<run id>-<check>-<style>`).
SPREFIX=sy2
SDIR_NAME=symbols-sc2

setup_file() {
  stamp_check
  SDIR="$(container_tmpdir "$SDIR_NAME")"
  RUN_ID="${SDIR##*.}"
  SROOT="$(scratch_root)"
  export SDIR RUN_ID SROOT
}

teardown_file() {
  container_rm "${SDIR:-}"
  rm_sessions
}

# ── helpers (this file's own; the 011 files repeat them so each reads alone) ─────────────────────

# scratch_root — the container's session scratch root, read in the container, never assumed.
scratch_root() {
  local r
  r="$(exec_plain sh -c 'printf "%s" "${TIMELIKE_SCRATCH_ROOT:-/tmp/timelike}"')" || return 1
  [[ "$r" == /?* ]] || { echo "scratch root in the container: '${r}'" >&2; return 1; }
  printf '%s' "$r"
}

# rm_sessions — remove this run's session directories (SROOT/SPREFIX-RUN_ID-*) and nothing else.
rm_sessions() {
  [[ -n "${RUN_ID:-}" && "${SROOT:-}" == /tmp/?* ]] || return 0
  exec_plain sh -c 'for d in "$1/$2-$3-"*; do [ -d "$d" ] && rm -rf -- "$d"; done; exit 0' \
    rm "$SROOT" "$SPREFIX" "$RUN_ID" >/dev/null 2>&1 || true
}

# new_cell NAME STYLE — this cell's workspace (CELL: a fresh directory holding `.git`, so it is the
# workspace root, FR-1; CELL.stderr beside it, outside the workspace) and its own session (SESSION),
# which must have no records yet.
new_cell() {
  CELL="${SDIR}/$1-$2"
  SESSION="${SPREFIX}-${RUN_ID}-$1-$2"
  exec_plain mkdir "$CELL" || { echo "cell path ${CELL} exists: cells must not share a workspace" >&2; return 1; }
  exec_plain mkdir "${CELL}/.git" || return 1
  if exec_plain test -e "${SROOT}/${SESSION}"; then
    echo "session ${SESSION} already has records: cells must not share a session" >&2
    return 1
  fi
}

# put RELPATH CONTENT — write CONTENT and a final newline to CELL/RELPATH with the container's printf
# (P005), making its directory first.
put() {
  exec_plain sh -c 'mkdir -p "$(dirname "$1")" && printf "%s\n" "$2" >"$1"' put "${CELL}/$1" "$2"
}

# bump RELPATH — move CELL/RELPATH's mtime 5 seconds forward, so a change is never hidden by the
# clock's granularity.
bump() {
  exec_plain "$AGENT_PY" -I -c 'import os, sys
st = os.stat(sys.argv[1])
os.utime(sys.argv[1], ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))' "${CELL}/$1"
}

# in_session [-e K=V]... STYLE CMD — run CMD in the workspace as the agent would, in this cell's
# session; stderr goes to CELL.stderr so stdout stays one document.
in_session() {
  local -a envs=()
  while [[ "${1:-}" == -e ]]; do
    envs+=(-e "$2")
    shift 2
  done
  run_in -e "TIMELIKE_SESSION=${SESSION}" "${envs[@]}" "$1" notty "{ cd '${CELL}' && $2; } 2>>'${CELL}.stderr'"
  assert_within 20
}

# flunk MESSAGE — fail with the last run's exit, stdout and stderr.
flunk() {
  local err
  err="$(exec_plain cat "${CELL}.stderr" 2>&1)" || true
  printf '%s\nexit %s; stdout:\n%s\nstderr:\n%s\n' "$1" "$status" "$output" "$err" >&2
  return 1
}

expect_status() {
  [[ "$status" == "$1" ]] || flunk "expected exit $1, got $status"
}

# jpy SCRIPT — Python over the last run's stdout, parsed as JSON into `d`; `g(k)` reads a field by a
# dotted path, top-level first, then under `data`; `rel(p)` strips the workspace (WS) from a path, so
# a path given absolute or relative compares the same. Output in $JPY.
jpy() {
  JPY="$(printf '%s' "$output" | pyq "import json,sys
WS='${CELL}'
d=json.load(sys.stdin)
def g(k, default='<absent>'):
    cur = d
    for i, part in enumerate(k.split('.')):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif i == 0 and part in (d.get('data') or {}):
            cur = d['data'][part]
        else:
            return default
    return cur
def rel(p):
    p = str(p)
    return p[len(WS) + 1:] if p.startswith(WS + '/') else p
$1")" || flunk "stdout is not the JSON expected"
}

jval() {
  local line
  while IFS= read -r line; do
    if [[ "$line" == "$1="* ]]; then
      printf '%s' "${line#"$1="}"
      return 0
    fi
  done <<<"$JPY"
  printf '<absent>'
}

expect_j() {
  local got
  got="$(jval "$1")"
  [[ "$got" == "$2" ]] || flunk "$1: expected '$2', got '$got'"
}

# expect_has WHAT TEXT PART… — TEXT contains every PART.
expect_has() {
  local what="$1" text="$2" part
  shift 2
  for part in "$@"; do
    [[ "$text" == *"$part"* ]] || flunk "${what} does not name '${part}': ${text}"
  done
}

# expect_verdict_ends WHAT VERDICT ERE — the cache clause ends the verdict (contract: "Every verdict
# ends with the cache state"; notes come before it). ERE is matched at the very end, after `; `.
expect_verdict_ends() {
  [[ "$2" =~ \;\ ($3)$ ]] || flunk "$1 does not end with the cache clause /; $3/: $2"
}

# text_line PREFIX — the first line of the last run's output starting with PREFIX (or nothing).
text_line() {
  local line
  for line in "${lines[@]}"; do
    if [[ "$line" == "$1"* ]]; then
      printf '%s' "$line"
      return 0
    fi
  done
}

# body_lines — the last run's text lines after the `verdict:` line, blank lines dropped, into BODY.
body_lines() {
  local line seen=0
  BODY=()
  for line in "${lines[@]}"; do
    if ((seen)); then
      [[ -n "${line// /}" ]] && BODY+=("$line")
    elif [[ "$line" == "verdict: "* ]]; then
      seen=1
    fi
  done
  ((seen)) || flunk "no verdict: line in the text output"
}

# ── fixtures ──────────────────────────────────────────────────────────────────────────────────

STORE_PY="$(
  cat <<'PY'
"""Storage."""


def persist(record, *, flush: bool = True) -> bool:
    return bool(record)
PY
)"

ORDERS_PY="$(
  cat <<'PY'
class Order:
    def persist(self) -> None:
        # def persist(): in a comment is not a definition
        note = "def persist(x): in a string is not one either"
        return None
PY
)"

UTIL_PY="$(
  cat <<'PY'
def outer(items):
    def persist(item):
        return item

    return [persist(i) for i in items]
PY
)"

PERSIST_JS="$(
  cat <<'JS'
// storage for the browser
function persist(record) {
  return record;
}
JS
)"

# The four definitions of `persist`, ranked as R4 / FR-5 state: FILE:LINE.
RANKED=("lib/store.py:4" "app/orders.py:2" "app/util.py:2" "web/persist.js:2")
UNKNOWN=no_such_symbol_q7

new_ranking_cell() {
  new_cell "$1" "$2"
  put lib/store.py "$STORE_PY"
  put app/orders.py "$ORDERS_PY"
  put app/util.py "$UTIL_PY"
  put web/persist.js "$PERSIST_JS"
}

# GEN_PY ROOT — the 1,000-file repository (research R1's shape), with needle_0500 at pkg10/mod0500.py:3.
GEN_PY="$(
  cat <<'PY'
import os, sys
root = sys.argv[1]
for i in range(1000):
    d = os.path.join(root, "pkg%02d" % (i // 50))
    os.makedirs(d, exist_ok=True)
    out = ['"""module %04d"""' % i, ""]
    if i == 500:
        out += ["def needle_0500(x):", "    return x", "", ""]
    for c in range(3):
        out.append("class Thing%d_%04d:" % (c, i))
        for m in range(4):
            out += ["    def method_%d(self, value):" % m, "        return value + %d" % m, ""]
        out.append("")
    for f in range(5):
        out += ["def helper_%d(a, b=None):" % f, "    return a", "", ""]
    with open(os.path.join(d, "mod%04d.py" % i), "w") as fh:
        fh.write("\n".join(out) + "\n")
PY
)"

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_def_json STYLE — the four definitions, best first, the stated ranking.
check_def_json() {
  new_ranking_cell json "$1"
  in_session "$1" "symbols def persist --json"
  expect_status 0
  local want
  want="$(printf '"%s",' "${RANKED[@]}")"
  jpy "want = [${want}]
defs = g('definitions', []) or []
got = ['%s:%s' % (rel(x.get('path')), x.get('line')) for x in defs]
print('got=' + json.dumps(got))
print('first=' + (got[0] if got else '<none>'))
prec = [str(x.get('precision')) for x in defs]
print('prec_text=' + json.dumps(['text-based' in p for p in prec]))
print('scope=' + str(g('scope')))"
  expect_j first "${RANKED[0]}"
  expect_j got "[$(printf '"%s", ' "${RANKED[@]}" | sed 's/, $//')]"
  expect_j prec_text '[false, false, false, true]'
  expect_has "the scope" "$(jval scope)" "4 definitions" "mixed"
}

# check_def_text STYLE — the first answer line is the best definition's FILE:LINE.
check_def_text() {
  new_ranking_cell text "$1"
  in_session "$1" "symbols def persist --text"
  expect_status 0
  [[ "${lines[0]:-}" == "symbols: "* ]] || flunk "the first line is not the header"
  body_lines
  ((${#BODY[@]} >= 1)) || flunk "no answer line after the verdict"
  [[ "${BODY[0]}" =~ ^lib/store\.py:4([^0-9]|$) ]] || flunk "the first answer line is not lib/store.py:4: ${BODY[0]}"
  local i n=0
  for i in "${!BODY[@]}"; do
    [[ "${BODY[$i]}" =~ ^([^[:space:]]+:[0-9]+)[[:space:]] ]] || continue
    [[ "${BASH_REMATCH[1]}" == "${RANKED[$n]:-<none>}" ]] ||
      flunk "answer $((n + 1)): want ${RANKED[$n]:-no more answers}, got ${BASH_REMATCH[1]}"
    n=$((n + 1))
  done
  ((n == ${#RANKED[@]})) || flunk "${n} answer lines, want ${#RANKED[@]}"
}

# check_not_found STYLE — an unknown name exits 3, under --json and --text.
check_not_found() {
  new_ranking_cell notfound "$1"
  in_session "$1" "symbols def ${UNKNOWN} --json"
  expect_status 3
  jpy "print('scope=' + str(g('scope')))
print('verdict=' + str(g('verdict')))
print('defs=' + json.dumps(g('definitions', [])))"
  expect_has "the JSON scope" "$(jval scope)" "not found"
  expect_has "the JSON verdict" "$(jval verdict)" "no definition of ${UNKNOWN} in 4 indexed files"
  [[ "$(jval defs)" == "[]" || "$(jval defs)" == '"<absent>"' ]] || flunk "definitions on not found: $(jval defs)"
  in_session "$1" "symbols def ${UNKNOWN} --text"
  expect_status 3
  expect_has "the header" "${lines[0]:-}" "symbols: " "not found"
  expect_has "the verdict" "$(text_line "verdict: ")" "no definition of ${UNKNOWN} in 4 indexed files"
  local err
  err="$(exec_plain cat "${CELL}.stderr")" || true
  [[ "${output}${err}" == *"search -w ${UNKNOWN}"* ]] || flunk "neither stdout nor stderr says 'search -w ${UNKNOWN}'"
}

# check_warm STYLE — a 1,000-file repository: cold call, then the warm call timed in the container.
check_warm() {
  new_cell warm "$1"
  exec_plain "$AGENT_PY" -I -c "$GEN_PY" "$CELL" || flunk "could not generate the 1,000-file repository"
  local n
  n="$(exec_plain sh -c 'find "$1" -name "*.py" -type f | wc -l' find "$CELL")"
  [[ "${n//[[:space:]]/}" == 1000 ]] || flunk "the generator wrote ${n} files, not 1000"
  in_session "$1" "symbols def needle_0500 --json"
  expect_status 0
  jpy "defs = g('definitions', []) or []
print('first=' + ('%s:%s' % (rel(defs[0].get('path')), defs[0].get('line')) if defs else '<none>'))
print('verdict=' + str(g('verdict')))"
  expect_j first "pkg10/mod0500.py:3"
  expect_verdict_ends "the cold verdict" "$(jval verdict)" "cache: built \\(1000 files\\)"
  in_session -e "SY_OUT=${CELL}.out" "$1" 's=$EPOCHREALTIME; symbols def needle_0500 --text >"$SY_OUT"; rc=$?; e=$EPOCHREALTIME; s=${s/[.,]/}; e=${e/[.,]/}; printf "rc=%s\nus=%s\n" "$rc" "$((10#$e - 10#$s))"; cat "$SY_OUT"'
  expect_status 0
  [[ "$(value_of rc)" == 0 ]] || flunk "the warm call exited $(value_of rc)"
  local us
  us="$(value_of us)"
  [[ "$us" =~ ^[0-9]+$ ]] || flunk "no measurement from the container: ${us}"
  ((us < 2000000)) || flunk "the warm call took $((us / 1000)) ms in the container, the bound is 2000 ms"
  expect_verdict_ends "the warm verdict" "$(text_line "verdict: ")" "cache: fresh"
  body_lines
  [[ "${BODY[0]:-}" =~ ^pkg10/mod0500\.py:3([^0-9]|$) ]] || flunk "the warm first answer line is not pkg10/mod0500.py:3: ${BODY[0]:-<none>}"
  echo "# warm def on 1,000 files: $((us / 1000)) ms in the container, ${ELAPSED_S}s at the runner" >&3
}

@test "SC-2 [bash -c, notty] A definition lookup returns the defining file and line first — JSON: four definitions in the stated ranking, exact before text-based, mixed scope" { check_def_json c; }
@test "SC-2 [bash -lc, notty] A definition lookup returns the defining file and line first — JSON: four definitions in the stated ranking, exact before text-based, mixed scope" { check_def_json lc; }
@test "SC-2 [bash -c, notty] A definition lookup returns the defining file and line first — text: the first answer line is lib/store.py:4, then the ranked rest" { check_def_text c; }
@test "SC-2 [bash -lc, notty] A definition lookup returns the defining file and line first — text: the first answer line is lib/store.py:4, then the ranked rest" { check_def_text lc; }
@test "SC-2 [bash -c, notty] A definition lookup exits 3 when the symbol is not found — JSON and text, scope not found, the indexed count, search -w" { check_not_found c; }
@test "SC-2 [bash -lc, notty] A definition lookup exits 3 when the symbol is not found — JSON and text, scope not found, the indexed count, search -w" { check_not_found lc; }
@test "SC-2 [bash -c, notty] A definition lookup answers in under 2 seconds warm on a 1,000-file repository — timed in the container after one cold call" { check_warm c; }
@test "SC-2 [bash -lc, notty] A definition lookup answers in under 2 seconds warm on a 1,000-file repository — timed in the container after one cold call" { check_warm lc; }
