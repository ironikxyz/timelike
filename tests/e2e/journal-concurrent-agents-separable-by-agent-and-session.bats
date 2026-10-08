#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-4 — "Entries from concurrent agents are separable by agent and session". (Feature 009, slice 1;
# spec FR-2, FR-5, FR-6, FR-7, FR-10, Scenario 4; tasks.md T004; contracts/journal-cli.md § Target,
# scope, verdict (labels), § JSON; research R1, R2, R7.)
#
# Written from the contract before the tool existed. Every expected value is the test's own (P004).
# Scenario 4, with two agents working at the same time in one container, each a loop of `docker exec`s
# run from the runner in the background (a harness's own invocation), each with its own TIMELIKE_AGENT:
#   a1, in session s1:  view a1-1, exit 21, view a1-2, [waits for a2 to reach s1], view a1-3, exit 22,
#                       view a1-4, view a1-5
#   a2, in session s2:  view a2-1, exit 31; then in session s1: view a2-2, exit 32, view a2-3
# The wait is a runner-side gate (a file a2 creates as it moves to s1), so a2's s1 work starts while a1
# is still working: a2's s1 entries fall between a1's first and last, every run. Each command's exit
# status is checked against the one it must have (view 0, `exit N` N). The names carry this run's id and
# the cell's style (`a1-<run id>-<style>`, sessions `j4-<run id>-<check>-<style>-s1`), so no other cell's
# records match. The journal is read from a third session, `…-reader`, with no agent, so the reads add
# nothing to s1 or s2.
#   - `journal --session s1 --agent a1 --all --json`: exactly a1's seven entries, in order: kind (view:
#     tool; `exit N`: shell), style, agent a1, session s1, exit and command;
#   - `journal --session s1 --agent a2 --all --json`: exactly a2's three s1 entries (none from s2);
#   - `journal --session s1 --all --json`: a1's and a2's, ten; `agents` names both; an a2 entry starts
#     between a1's first and last (they were concurrent);
#   - `journal --all-sessions --all --json`: every entry carries an `agent` field and a non-empty
#     `session` (an entry whose record names no agent, from another session, may carry null: FR-10 shows
#     it as `-`); s1's entries are exactly a1's seven and a2's three, s2's exactly a2's two, each
#     agent's in its own order;
#   - `journal --all-sessions --all --agent a2 --text`: five entry lines, each labelled `[a2/s2]` or
#     `[a2/s1]` after the time, in order.
#
# Fixtures are made by running real tools and shells in the container (P005); no record is written by
# the test. Shell entries (`exit N`) are written by the image's hook, so this file needs the image: a
# host stand-in without the hook has no shell entries, and fails here.
# teardown_file removes this run's session directories (prefix `j4-<run id>-`) and nothing else.
# Cells: bash -c and bash -lc, `notty`.

load helpers

# This file's session prefix (sessions are `<prefix>-<run id>-<check>-<style>[-s1|-s2|-reader]`).
JPREFIX=j4

setup_file() {
  stamp_check
  JDIR="$(container_tmpdir journal-sc4)"
  RUN_ID="${JDIR##*.}"
  SROOT="$(scratch_root)"
  export JDIR RUN_ID SROOT
}

teardown_file() {
  container_rm "${JDIR:-}"
  rm_sessions "$JPREFIX"
}

# ── helpers (this file's own; the 009 files repeat them so each reads alone) ─────────────────────

# scratch_root — the container's session scratch root, read in the container, never assumed.
scratch_root() {
  local r
  r="$(exec_plain sh -c 'printf "%s" "${TIMELIKE_SCRATCH_ROOT:-/tmp/timelike}"')" || return 1
  [[ "$r" == /?* ]] || { echo "scratch root in the container: '${r}'" >&2; return 1; }
  printf '%s' "$r"
}

# rm_sessions PREFIX — remove this run's session directories (SROOT/PREFIX-RUN_ID-*) and nothing else.
rm_sessions() {
  [[ -n "${RUN_ID:-}" && "${SROOT:-}" == /tmp/?* ]] || return 0
  exec_plain sh -c 'for d in "$1/$2-$3-"*; do [ -d "$d" ] && rm -rf -- "$d"; done; exit 0' \
    rm "$SROOT" "$1" "$RUN_ID" >/dev/null 2>&1 || true
}

# new_cell NAME STYLE — this cell's fixture directory (CELL, with CELL.stderr beside it) and its own
# session (SESSION), which must have no records yet.
new_cell() {
  CELL="${JDIR}/$1-$2"
  SESSION="${JPREFIX}-${RUN_ID}-$1-$2"
  exec_plain mkdir "$CELL" || { echo "cell path ${CELL} exists: cells must not share a fixture" >&2; return 1; }
  if exec_plain test -e "${SROOT}/${SESSION}"; then
    echo "session ${SESSION} already has records: cells must not share a session" >&2
    return 1
  fi
}

# put PATH FORMAT — write FORMAT with the container's printf (P005). FORMAT carries no % directive.
put() {
  [[ "$2" != *%* ]] || { echo "put: FORMAT carries a %" >&2; return 1; }
  exec_plain sh -c 'printf "$2" >"$1"' put "$1" "$2"
}

# in_session [-e K=V]... STYLE CMD — run CMD as the agent would, in this cell's session; stderr goes to
# CELL.stderr so stdout stays one document.
in_session() {
  local -a envs=()
  while [[ "${1:-}" == -e ]]; do
    envs+=(-e "$2")
    shift 2
  done
  run_in -e "TIMELIKE_SESSION=${SESSION}" "${envs[@]}" "$1" notty "$2 2>>'${CELL}.stderr'"
  assert_within 20
}

# timed STYLE CMD — in_session, with the runner-side window around it appended to T_BEFORE / T_AFTER.
timed() {
  local b
  b="$(now_ms)"
  in_session "$1" "$2"
  T_BEFORE+=("$b")
  T_AFTER+=("$(now_ms)")
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
# dotted path, top-level first, then under `data`. Output in $JPY.
jpy() {
  JPY="$(printf '%s' "$output" | pyq "import json,sys
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
$1")" || flunk "stdout is not the JSON expected"
}

# jfields KEY... — KEY=VALUE lines into $JPY (strings raw, everything else as JSON).
jfields() {
  local ks
  ks="$(printf '"%s",' "$@")"
  jpy "for k in [${ks}]:
    v = g(k)
    print(k + '=' + (v if isinstance(v, str) else json.dumps(v, sort_keys=True)))"
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

# ENTRIES_PY — one line per JSON entry, tab-separated:
#   kind style agent session exit command ref start_ms end_ms
# `command` is the shell's own command line for a shell entry, and for any other entry the JSON list of
# the words a shell would split it into (shlex), so tool and arguments compare exactly whatever quoting
# the tool chose. `ref` is `key=value` pairs, sorted. A time that is not ISO 8601 UTC with milliseconds
# prints as `bad:<value>`. An empty or null field prints as <none>.
ENTRIES_PY="$(
  cat <<'PY'
import datetime, re, shlex
ISO = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}(Z|\+00:00)$')
def ms(t):
    if not isinstance(t, str) or not ISO.match(t):
        return 'bad:' + repr(t)
    return str(round(datetime.datetime.fromisoformat(t.replace('Z', '+00:00')).timestamp() * 1000))
def ref(r):
    if isinstance(r, dict):
        return ' '.join('%s=%s' % (k, r[k]) for k in sorted(r))
    return r
def s(v):
    if v is None or v == '':
        return '<none>'
    v = v if isinstance(v, str) else json.dumps(v, sort_keys=True)
    return v.replace('\t', ' ').replace('\n', ' ')
for e in g('entries', []) or []:
    c = e.get('command')
    if e.get('kind') != 'shell' and isinstance(c, str):
        try:
            c = json.dumps(shlex.split(c))
        except ValueError:
            pass
    print('\t'.join(s(x) for x in (e.get('kind'), e.get('style'), e.get('agent'), e.get('session'),
                                   e.get('exit'), c, ref(e.get('ref')), ms(e.get('start')), ms(e.get('end')))))
PY
)"

# jentries — the last run's entries into ENTRIES (one line each, ENTRIES_PY's form).
jentries() {
  jpy "$ENTRIES_PY"
  ENTRIES=()
  [[ -z "$JPY" ]] || mapfile -t ENTRIES <<<"$JPY"
}


# An entry line in text: it starts with the time (date lines start with `──`).
ENTRY_LINE_RE='^[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3} '

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# wl FIELD... — FIELDs joined by tabs.
wl() {
  local IFS=$'\t'
  printf '%s' "$*"
}

# fresh SESSION — no records yet.
fresh() {
  if exec_plain test -e "${SROOT}/$1"; then
    echo "session $1 already has records: cells must not share a session" >&2
    return 1
  fi
}

# agent_loop STYLE AGENT STEP... — one `docker exec` per STEP, in order, as AGENT. A STEP is
# `SESSION view NAME` (view CELL/NAME.txt), `SESSION exit N`, `gate` (wait up to 20 s for the
# runner-side GATE file) or `open` (create it). A status other than the one the step must have is
# appended to FAILS. Runs in the background: it uses exec_in, not run_in.
agent_loop() {
  local style="$1" agent="$2" step sess what arg want rc n
  shift 2
  for step in "$@"; do
    read -r sess what arg <<<"$step"
    case "$sess" in
      gate)
        for ((n = 0; n < 200; n++)); do
          [[ -e "$GATE" ]] && break
          sleep 0.1
        done
        [[ -e "$GATE" ]] || echo "${agent}: the gate never opened" >>"$FAILS"
        continue
        ;;
      open)
        : >"$GATE"
        continue
        ;;
    esac
    if [[ "$what" == view ]]; then
      want=0
      exec_in -e "TIMELIKE_SESSION=${sess}" -e "TIMELIKE_AGENT=${agent}" "$style" notty \
        "view ${CELL}/${arg}.txt >/dev/null 2>&1" >/dev/null 2>&1 && rc=0 || rc=$?
    else
      want="$arg"
      exec_in -e "TIMELIKE_SESSION=${sess}" -e "TIMELIKE_AGENT=${agent}" "$style" notty \
        "exit ${arg}" >/dev/null 2>&1 && rc=0 || rc=$?
    fi
    ((rc == want)) || echo "${agent} in ${sess}: '${what} ${arg}' exited ${rc}, want ${want}" >>"$FAILS"
  done
}

# want_of STYLE AGENT STEP... — the entries the steps must produce (ENTRIES_PY's first six fields:
# kind, style, agent, session, exit, command), one per line, gates left out.
want_of() {
  local st agent="$2" step sess what arg
  st="$(style_label "$1")"
  shift 2
  for step in "$@"; do
    read -r sess what arg <<<"$step"
    case "$what" in
      view) wl tool "$st" "$agent" "$sess" 0 "[\"view\", \"${CELL}/${arg}.txt\"]" ;;
      exit) wl shell "$st" "$agent" "$sess" "$arg" "exit ${arg}" ;;
      *) continue ;;
    esac
    printf '\n'
  done
}

# six LINE — the first six fields of an ENTRIES line.
six() {
  local a b c d e f
  IFS=$'\t' read -r a b c d e f _ <<<"$1"
  wl "$a" "$b" "$c" "$d" "$e" "$f"
}

# expect_entries WHAT WANT(newline-separated) LINE... — the lines' first six fields equal WANT, in order.
expect_entries() {
  local what="$1" want="$2" got="" l
  shift 2
  for l in "$@"; do
    got+="$(six "$l")"$'\n'
  done
  [[ "$got" == "$want" ]] || flunk "${what}:
got:
${got//$'\t'/ | }want:
${want//$'\t'/ | }"
}

# read_journal ARGS — `journal ARGS` from the reader session (no agent).
read_journal() {
  run_in -e "TIMELIKE_SESSION=${READER}" "$1" notty "journal $2 2>>'${CELL}.stderr'"
  assert_within 20
  expect_status 0
}

# check_sc4 STYLE — the two agents, concurrently; then the five reads.
check_sc4() {
  local style="$1"
  new_cell sc4 "$style"
  local s1="${SESSION}-s1" s2="${SESSION}-s2" a1="a1-${RUN_ID}-${style}" a2="a2-${RUN_ID}-${style}"
  READER="${SESSION}-reader"
  fresh "$s1"
  fresh "$s2"
  fresh "$READER"
  exec_plain sh -c 'for f in a1-1 a1-2 a1-3 a1-4 a1-5 a2-1 a2-2 a2-3; do printf "%s\n" "$f" >"$1/$f.txt"; done' put "$CELL"
  GATE="${BATS_TEST_TMPDIR}/gate"
  FAILS="${BATS_TEST_TMPDIR}/fails"
  : >"$FAILS"

  local -a a1_steps=("$s1 view a1-1" "$s1 exit 21" "$s1 view a1-2" gate "$s1 view a1-3" "$s1 exit 22" "$s1 view a1-4" "$s1 view a1-5")
  local -a a2_s2=("$s2 view a2-1" "$s2 exit 31")
  local -a a2_s1=("$s1 view a2-2" "$s1 exit 32" "$s1 view a2-3")

  agent_loop "$style" "$a1" "${a1_steps[@]}" 3>&- &
  local p1=$!
  agent_loop "$style" "$a2" "${a2_s2[@]}" open "${a2_s1[@]}" 3>&- &
  local p2=$!
  wait "$p1" || true
  wait "$p2" || true
  [[ ! -s "$FAILS" ]] || flunk "the agents' commands did not exit as made:
$(cat "$FAILS")"

  local want_a1 want_a2_s1 want_a2_s2
  want_a1="$(want_of "$style" "$a1" "${a1_steps[@]}")"$'\n'
  want_a2_s1="$(want_of "$style" "$a2" "${a2_s1[@]}")"$'\n'
  want_a2_s2="$(want_of "$style" "$a2" "${a2_s2[@]}")"$'\n'

  # 1. s1, agent a1: a1's entries only.
  read_journal "$style" "--session ${s1} --agent ${a1} --all --json"
  jentries
  expect_entries "journal --session s1 --agent a1" "$want_a1" "${ENTRIES[@]}"

  # 2. s1, agent a2: a2's s1 entries only, none from s2.
  read_journal "$style" "--session ${s1} --agent ${a2} --all --json"
  jentries
  expect_entries "journal --session s1 --agent a2" "$want_a2_s1" "${ENTRIES[@]}"

  # 3. s1, every agent: both, interleaved; `agents` names both.
  read_journal "$style" "--session ${s1} --all --json"
  jpy "print('agents=' + json.dumps(sorted(g('agents', []) or [])))"
  expect_j agents "[\"${a1}\", \"${a2}\"]"
  jentries
  ((${#ENTRIES[@]} == 10)) || flunk "session s1 lists ${#ENTRIES[@]} entries, want a1's 7 and a2's 3"
  local e agent start first="" last="" between=0
  local -a e1=() e2=()
  for e in "${ENTRIES[@]}"; do
    IFS=$'\t' read -r _ _ agent _ _ _ _ start _ <<<"$e"
    if [[ "$agent" == "$a1" ]]; then
      e1+=("$e")
      [[ -n "$first" ]] || first="$start"
      last="$start"
    else
      e2+=("$e")
    fi
  done
  expect_entries "session s1, a1's entries in the merged list" "$want_a1" "${e1[@]}"
  expect_entries "session s1, a2's entries in the merged list" "$want_a2_s1" "${e2[@]}"
  for e in "${e2[@]}"; do
    IFS=$'\t' read -r _ _ _ _ _ _ _ start _ <<<"$e"
    ((start > first && start < last)) && between=1
  done
  ((between == 1)) || flunk "no a2 entry starts between a1's first (${first}) and last (${last}): the agents did not overlap"

  # 4. Every session: every entry labelled with its agent and session; ours separated exactly.
  read_journal "$style" "--all-sessions --all --json"
  jpy "print('unlabelled=' + str(sum(1 for e in (g('entries', []) or []) if 'agent' not in e or 'session' not in e)))"
  expect_j unlabelled 0
  jentries
  local session
  local -a in_s1_a1=() in_s1_a2=() in_s2=()
  for e in "${ENTRIES[@]}"; do
    IFS=$'\t' read -r _ _ agent session _ _ _ _ _ <<<"$e"
    [[ "$session" != '<none>' ]] || flunk "an entry without its session: ${e//$'\t'/ | }"
    case "$session" in
      "$s1") if [[ "$agent" == "$a1" ]]; then in_s1_a1+=("$e"); else in_s1_a2+=("$e"); fi ;;
      "$s2") in_s2+=("$e") ;;
    esac
  done
  expect_entries "--all-sessions, session s1, agent a1" "$want_a1" "${in_s1_a1[@]}"
  expect_entries "--all-sessions, session s1, every other agent" "$want_a2_s1" "${in_s1_a2[@]}"
  expect_entries "--all-sessions, session s2" "$want_a2_s2" "${in_s2[@]}"

  # 5. Text: a2's entries across sessions, each labelled [agent/session] after the time.
  run_in -e "TIMELIKE_SESSION=${READER}" -e COLUMNS=1000 "$style" notty \
    "journal --all-sessions --all --agent ${a2} --text 2>>'${CELL}.stderr'"
  assert_within 20
  expect_status 0
  local line i
  local -a el=()
  for line in "${lines[@]}"; do
    [[ "$line" =~ $ENTRY_LINE_RE ]] && el+=("$line")
  done
  local -a want_lab=("[${a2}/${s2}]" "[${a2}/${s2}]" "[${a2}/${s1}]" "[${a2}/${s1}]" "[${a2}/${s1}]")
  local -a want_txt=(a2-1.txt "exit 31" a2-2.txt "exit 32" a2-3.txt)
  ((${#el[@]} == 5)) || flunk "${#el[@]} entry lines for a2 across sessions, want 5"
  for ((i = 0; i < 5; i++)); do
    [[ "${el[i]}" =~ ^[0-9:.]+\ +(.*)$ && "${BASH_REMATCH[1]}" == "${want_lab[i]} "* ]] ||
      flunk "line $((i + 1)) is not labelled ${want_lab[i]} after the time: ${el[i]}"
    [[ "${el[i]}" == *"${want_txt[i]}"* ]] || flunk "line $((i + 1)) is not a2's '${want_txt[i]}': ${el[i]}"
  done
}

@test "SC-4 [bash -c, notty] Entries from concurrent agents are separable by agent and session — a1 in s1, a2 in s2 then s1, concurrently: --session s1 --agent a1 only a1's; --all-sessions labels every entry" { check_sc4 c; }
@test "SC-4 [bash -lc, notty] Entries from concurrent agents are separable by agent and session — a1 in s1, a2 in s2 then s1, concurrently: --session s1 --agent a1 only a1's; --all-sessions labels every entry" { check_sc4 lc; }
