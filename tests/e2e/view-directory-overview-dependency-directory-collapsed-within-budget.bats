#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-6 — "A directory overview of a repository with a dependency directory of 10,000 files fits its
# default budget, collapses that directory to one line with counts, and names how to expand it".
# (Feature 006, slice 1; spec FR-24 to FR-31; tasks.md T018; contracts/view-search-cli.md § Slice 1,
# `view DIR`.)
#
# Written from the contract before the tool existed (tasks.md Phase 6, tests first). The test decides by
# what it measures itself (lore cross-stack P004, P005): the repository is a real one made by git, its
# node_modules/ is written by the test (10,000 files in 200 directories), and the fixture counts both
# with find. The expected overview is rendered by this file's own oracle, the image's Python over
# os.walk/os.listdir, from the contract's rules: directories first, then files, each group sorted by
# name (str order), two spaces per level, `name  SIZE` with 003's size rule, and the two collapsed
# lines with counts the oracle took itself; singular words follow the oracle's own count (the
# contract's "singulars everywhere"). Which entries are ignored is the fixture's, confirmed there by
# `git check-ignore`, never by the tool.
#
# The fixture is built by fixtures/bounded-read-slice1.sh (`overview`), afresh per test.
# Cells: bash -c and bash -lc, `notty`.

load helpers

FIXTURE=/tmp/bounded-read-slice1-sc6.sh

# The oracle: argv[1] is the repository. Prints KEY=VALUE lines and `body:<line>` for each expected
# overview line of `view .` run in the repository.
#   F D B         totals under the repository: files, dirs, bytes of regular files, everything below
#                 it (.git and node_modules included) except the ignored files that are not listed
#                 (debug.log), which the verdict counts apart as I (ASSUMED: the contract does not say
#                 whether F includes them; "I ignored files not listed" reads as a separate count)
#   I             ignored files not listed
#   VERDICT       the whole verdict, with the kinds in FR-28's precedence order (vcs before dependency)
#   NM_F NM_D NM_S   node_modules' own totals (its expand view's verdict)
#   collapsed     JSON [[path, kind, files, dirs, bytes, complete, expand], ...] in line order
#   nm_line       the node_modules line exactly
#   nm_entries    node_modules' own entries, in order, space-separated
read -r -d '' OVERVIEW_ORACLE <<'PY' || true
import json, os, sys
os.chdir(sys.argv[1])
IGNORED_FILES = {"debug.log"}          # the fixture's: *.log, confirmed with git check-ignore
COLLAPSE = {".git": "vcs", "node_modules": "dependency"}

def human(n):
    if n < 1024:
        return "%d B" % n
    x = float(n)
    for unit in ("KiB", "MiB", "GiB", "TiB"):
        x /= 1024
        if x < 1024 or unit == "TiB":
            return "%.1f %s" % (x, unit)

def plural(n, word):
    return "%d %s" % (n, word if n == 1 else word + "s")

def is_dir(p):
    return os.path.isdir(p) and not os.path.islink(p)

def totals(path):
    files = dirs = size = 0
    for top, ds, fs in os.walk(path):
        dirs += len(ds)
        for f in fs:
            p = os.path.join(top, f)
            files += 1
            if os.path.isfile(p) and not os.path.islink(p):
                size += os.lstat(p).st_size
    return files, dirs, size

body, collapsed, skipped = [], [], [0, 0]

def render(rel, depth):
    names = sorted(os.listdir(rel or "."))
    ds = [n for n in names if is_dir(os.path.join(rel, n))]
    fs = [n for n in names if n not in ds]
    ind = "  " * depth
    for d in ds:
        path = os.path.join(rel, d) if rel else d
        if d in COLLAPSE:
            f, dd, s = totals(path)
            body.append("%s%s/  %s, %s, %s; %s — expand: view %s/" % (
                ind, d, plural(f, "file"), plural(dd, "dir"), human(s), COLLAPSE[d], path))
            collapsed.append([path, COLLAPSE[d], f, dd, s, True, "view %s/" % path])
        else:
            body.append("%s%s/" % (ind, d))
            render(path, depth + 1)
    for f in fs:
        path = os.path.join(rel, f) if rel else f
        if path in IGNORED_FILES:
            skipped[0] += 1
            skipped[1] += os.lstat(path).st_size
            continue
        body.append("%s%s  %s" % (ind, f, human(os.lstat(path).st_size)))

render("", 0)
assert len(body) <= 200, "the fixture does not fit the budget unaided"
F, D, B = totals(".")
F, B, I = F - skipped[0], B - skipped[1], skipped[0]
kinds = sorted({k for _, k, *_ in collapsed}, key=["vcs", "dependency", "build", "ignored", "budget"].index)
by_kind = ", ".join("%s %d" % (k, sum(1 for c in collapsed if c[1] == k)) for k in kinds)
nf, nd, nb = totals("node_modules")
print("F=%d" % F)
print("D=%d" % D)
print("B=%d" % B)
print("I=%d" % I)
print("VERDICT=%s, %s, %s under .; collapsed %d (%s); %s not listed" % (
    plural(F, "file"), plural(D, "dir"), human(B), len(collapsed), by_kind, plural(I, "ignored file")))
print("F_WORDS=%s, %s, %s" % (plural(F, "file"), plural(D, "dir"), human(B)))
print("NM_WORDS=%s, %s, %s" % (plural(nf, "file"), plural(nd, "dir"), human(nb)))
print("NM_F=%d" % nf)
print("NM_D=%d" % nd)
print("collapsed=" + json.dumps(collapsed))
print("nm_line=" + [b for b in body if b.startswith("node_modules/")][0])
print("nm_entries=" + " ".join(sorted(os.listdir("node_modules"))))
for line in body:
    print("body:" + line)
PY

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/bounded-read-slice1.sh" "$FIXTURE" 0755
}

setup() {
  WORK="$(container_tmpdir sc6overview)"
  FX="${WORK}/fx"
  REPO="${FX}/repo"
  SCRATCH="${WORK}/scratch"
  exec_plain sh "$FIXTURE" overview "$FX" >/dev/null
  oracle
}

teardown() {
  container_rm "$WORK"
}

# ── helpers (this file's own; the 006 files repeat them so each reads alone) ─────────────────────

# in_dir STYLE DIR CMD [K=V]... — run CMD in DIR with this test's session scratch; stderr goes to
# $WORK/stderr so stdout stays one JSON document.
in_dir() {
  local style="$1" dir="$2" cmd="$3" kv
  shift 3
  local -a envs=(-e "TIMELIKE_SCRATCH_ROOT=${SCRATCH}" -e "TIMELIKE_SESSION=boundedread")
  for kv in "$@"; do envs+=(-e "$kv"); done
  run_in "${envs[@]}" "$style" notty "cd '${dir}' && { ${cmd}; } 2>'${WORK}/stderr'"
  assert_within 20
}

# flunk MESSAGE — fail with the last run's exit, stdout and stderr.
flunk() {
  local err
  err="$(exec_plain cat "${WORK}/stderr" 2>&1)" || true
  printf '%s\nexit %s; stdout:\n%s\nstderr:\n%s\n' "$1" "$status" "$output" "$err" >&2
  return 1
}

expect_status() {
  [[ "$status" == "$1" ]] || flunk "expected exit $1, got $status"
}

# jpy SCRIPT — Python over the last run's stdout, parsed as JSON into `d`; `g(k)` reads a field by a
# dotted path (`truncated.more`), top-level first, then under `data`. Output in $JPY.
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

# json_lines — the JSON `lines` array, one per line, into $JPY.
json_lines() {
  jpy "print('\n'.join(g('lines', [])))"
}

# same_text WHAT EXPECTED GOT — equal, or fail naming the first line that differs.
same_text() {
  [[ "$2" == "$3" ]] && return 0
  local -a e g
  local i
  mapfile -t e <<<"$2"
  mapfile -t g <<<"$3"
  for ((i = 0; i < ${#e[@]} || i < ${#g[@]}; i++)); do
    if [[ "${e[i]-<none>}" != "${g[i]-<none>}" ]]; then
      flunk "$1: ${#g[@]} lines, want ${#e[@]}; first difference at line $((i + 1)): want '${e[i]-<none>}', got '${g[i]-<none>}'"
      return 1
    fi
  done
  flunk "$1 differs"
}

# ── the oracle ───────────────────────────────────────────────────────────────────────────────

# oracle — run OVERVIEW_ORACLE over the repository; set the O_* figures and EXPECTED_BODY.
oracle() {
  local out line body=()
  out="$(exec_plain "$AGENT_PY" -I -c "$OVERVIEW_ORACLE" "$REPO")" || { echo "the oracle failed: ${out}" >&2; return 1; }
  O_COLLAPSED="" O_NM_LINE="" O_NM_ENTRIES=""
  while IFS= read -r line; do
    case "$line" in
      body:*) body+=("${line#body:}") ;;
      F=*) O_F="${line#F=}" ;;
      D=*) O_D="${line#D=}" ;;
      B=*) O_B="${line#B=}" ;;
      I=*) O_I="${line#I=}" ;;
      VERDICT=*) O_VERDICT="${line#VERDICT=}" ;;
      NM_WORDS=*) O_NM_WORDS="${line#NM_WORDS=}" ;;
      NM_F=*) O_NM_F="${line#NM_F=}" ;;
      NM_D=*) O_NM_D="${line#NM_D=}" ;;
      collapsed=*) O_COLLAPSED="${line#collapsed=}" ;;
      nm_line=*) O_NM_LINE="${line#nm_line=}" ;;
      nm_entries=*) O_NM_ENTRIES="${line#nm_entries=}" ;;
    esac
  done <<<"$out"
  EXPECTED_BODY="$(printf '%s\n' "${body[@]}")"
  # The criterion's own number, counted by the oracle (not the fixture's word for it).
  [[ "$O_NM_F" == 10000 ]] || { echo "the oracle counts ${O_NM_F} files in node_modules, want 10000" >&2; return 1; }
  [[ "$O_NM_LINE" == *"10000 files"* ]] || { echo "oracle nm line: ${O_NM_LINE}" >&2; return 1; }
}

# overview_body — the text run's lines after the header and verdict, into $BODY and BODY_LINES.
overview_body() {
  BODY_LINES=("${lines[@]:2}")
  BODY="$(printf '%s\n' "${BODY_LINES[@]}")"
}

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_overview_text STYLE — `view --text .` in the repository: the header's scope is `overview`, the
# body is at most 200 lines and is exactly the oracle's tree; node_modules/ is exactly one line, with
# `10000 files` and `expand: view node_modules/`; .git/ is collapsed as vcs; the ignored debug.log is
# not listed; the verdict is exactly the oracle's: its totals, the two collapsed directories by kind
# in FR-28's precedence order (vcs, dependency), and the ignored files not listed.
check_overview_text() {
  in_dir "$1" "$REPO" "view --text ."
  expect_status 0
  [[ "${lines[0]:-}" == "view: . [overview]" ]] || flunk "header line: ${lines[0]:-<none>}"
  overview_body
  ((${#BODY_LINES[@]} <= 200)) || flunk "the overview prints ${#BODY_LINES[@]} body lines, over the default budget of 200"

  local line nm=() i
  for line in "${BODY_LINES[@]}"; do
    [[ "$line" == *"node_modules/"* ]] && nm+=("$line")
  done
  [[ ${#nm[@]} -eq 1 ]] || flunk "${#nm[@]} lines name node_modules/, want exactly 1"
  [[ "${nm[0]}" == *"10000 files"* ]] || flunk "the node_modules line lacks '10000 files': ${nm[0]}"
  [[ "${nm[0]}" == *"expand: view node_modules/" ]] || flunk "the node_modules line does not end with 'expand: view node_modules/': ${nm[0]}"
  [[ "${nm[0]}" == "$O_NM_LINE" ]] || flunk "the node_modules line: want '${O_NM_LINE}', got '${nm[0]}'"
  assert_no_line_matching '^ *debug\.log( |$)' || flunk "the ignored debug.log is listed"
  for ((i = 2; i < ${#lines[@]}; i++)); do
    [[ "${lines[i]}" != *pkg-0* ]] || flunk "a line inside node_modules is listed: ${lines[i]}"
  done

  same_text "the overview's body" "$EXPECTED_BODY" "$BODY"

  [[ "${lines[1]:-}" == "verdict: ${O_VERDICT}" ]] || flunk "verdict line: ${lines[1]:-<none>} (want 'verdict: ${O_VERDICT}')"
}

# check_overview_json STYLE — `view --json .`: overview true, scope overview, the oracle's totals as
# numbers, budget_lines 200, `collapsed` exactly the oracle's two entries in line order (node_modules
# kind dependency with 10000 files, complete), `lines` the same lines as the text body, at most 200.
check_overview_json() {
  local abs
  abs="$(exec_plain realpath "$REPO")"
  in_dir "$1" "$REPO" "view --text ."
  expect_status 0
  overview_body
  local text_body="$BODY" text_verdict="${lines[1]#verdict: }"

  in_dir "$1" "$REPO" "view --json ."
  expect_status 0
  jfields tool target scope verdict overview path abs_path files dirs bytes budget_lines ignored_files exit
  expect_j tool view
  expect_j target .
  expect_j scope overview
  expect_j verdict "$text_verdict"
  expect_j overview true
  expect_j path .
  expect_j abs_path "$abs"
  expect_j files "$O_F"
  expect_j dirs "$O_D"
  expect_j bytes "$O_B"
  expect_j budget_lines 200
  expect_j exit 0
  expect_j ignored_files "$O_I"

  # path is compared without a leading ./ or a trailing /, which the contract does not fix.
  jpy "c = g('collapsed', [])
rows = [[str(e.get('path')).removeprefix('./').rstrip('/'), e.get('kind'), e.get('files'), e.get('dirs'),
         e.get('bytes'), e.get('complete'), e.get('expand')] for e in c]
print('collapsed=' + json.dumps(rows))
nm = [e for e in c if str(e.get('path')).removeprefix('./').rstrip('/') == 'node_modules']
print('nm_kind=' + (nm[0].get('kind') if len(nm) == 1 else '<%d entries>' % len(nm)))
print('nm_files=' + (json.dumps(nm[0].get('files')) if len(nm) == 1 else '<absent>'))
print('nlines=%d' % len(g('lines', [])))"
  expect_j nm_kind dependency
  expect_j nm_files 10000
  expect_j collapsed "$O_COLLAPSED"
  (($(jval nlines) <= 200)) || flunk "JSON lines holds $(jval nlines) lines, over the budget of 200"
  json_lines
  same_text "JSON lines against the text body" "$text_body" "$JPY"
}

# check_expand_runs STYLE — the node_modules line's expand command, run exactly as printed in the
# same directory, shows node_modules' own entries: an overview of node_modules/ (never collapsed
# itself) whose top-level lines are the oracle's 100 package directories in order, within 200 lines,
# with node_modules' totals.
check_expand_runs() {
  in_dir "$1" "$REPO" "view --text ."
  expect_status 0
  local line expand=""
  for line in "${lines[@]}"; do
    if [[ "$line" == node_modules/* && "$line" == *" expand: "* ]]; then
      expand="${line##* expand: }"
    fi
  done
  [[ "$expand" == "view node_modules/" ]] || flunk "the expand command printed: '${expand}'"

  in_dir "$1" "$REPO" "$expand"
  expect_status 0
  jfields scope overview files dirs verdict
  expect_j scope overview
  expect_j overview true
  expect_j files "$O_NM_F"
  expect_j dirs "$O_NM_D"
  [[ "$(jval verdict)" == "${O_NM_WORDS} under node_modules/"* ]] \
    || flunk "verdict: $(jval verdict) (want it to start '${O_NM_WORDS} under node_modules/')"
  json_lines
  local -a got top=()
  mapfile -t got <<<"$JPY"
  ((${#got[@]} <= 200)) || flunk "the expanded view prints ${#got[@]} lines, over the budget of 200"
  for line in "${got[@]}"; do
    [[ "$line" == " "* ]] && continue
    [[ "$line" =~ ^([^/ ]+)/( |$) ]] || flunk "a top-level line of node_modules/ is not a directory: ${line}"
    [[ "$line" != *"; dependency — "* ]] || flunk "node_modules' own entry is collapsed as a dependency: ${line}"
    top+=("${BASH_REMATCH[1]}")
  done
  local got_top="${top[*]}"
  [[ "$got_top" == "$O_NM_ENTRIES" ]] || flunk "top-level entries: want '${O_NM_ENTRIES:0:60}…' (100), got ${#top[@]}: '${got_top:0:60}…'"
}

@test "SC-6 a directory overview of a repository with a dependency directory of 10,000 files fits its default budget, collapses that directory to one line with counts, and names how to expand it [bash -c, notty]" { check_overview_text c; }
@test "SC-6 a directory overview of a repository with a dependency directory of 10,000 files fits its default budget, collapses that directory to one line with counts, and names how to expand it [bash -lc, notty]" { check_overview_text lc; }
@test "SC-6 a directory overview: JSON carries the totals, budget_lines 200 and node_modules collapsed as a dependency with 10000 files [bash -c, notty]" { check_overview_json c; }
@test "SC-6 a directory overview: JSON carries the totals, budget_lines 200 and node_modules collapsed as a dependency with 10000 files [bash -lc, notty]" { check_overview_json lc; }
@test "SC-6 a directory overview: the expand command, run as printed, shows node_modules' own entries [bash -c, notty]" { check_expand_runs c; }
@test "SC-6 a directory overview: the expand command, run as printed, shows node_modules' own entries [bash -lc, notty]" { check_expand_runs lc; }
