#!/bin/sh
# Build the files and the repository for the 006 bounded-read tests (view and search; tasks.md T001).
# Runs INSIDE the agent container as the agent user:  sh /tmp/bounded-read-<tag>.sh DIR
#
# Content is made with seq, printf, awk and git only, never with view or search (lore cross-stack
# P005), and every count the tests rely on is checked at the end with grep and git, so a fixture that
# drifts fails here, at build time, not as a confusing test failure.
#
#   big.txt      412 distinct lines ("line NNN: ..."), varied lengths          (SC-1, SC-2)
#   small.txt    100 lines: fits the 120-line window, so it is shown whole     (SC-1)
#   long.txt     a short line, one line of exactly 5000 bytes, a short line    (FR-7, text cut)
#   app.bin      ELF magic, then NULs, then an ASCII marker                    (SC-2)
#   pic.png      PNG magic, then NULs, then an ASCII marker                    (SC-2)
#                The marker (BOUNDED_READ_CONTENT_MARKER) is content: it must never be printed.
#   latin1.txt   invalid UTF-8 (lone latin-1 bytes)                            (FR-10)
#   escapes.txt  two lines carrying terminal escape sequences                  (FR-11)
#   repo/        a real git repository, made with git:
#                .gitignore ignores build/ and *.log
#                needle_fn, one per line, exactly 262 times outside ignored paths and outside .git:
#                  docs/api.md 12, docs/guide.md 18 (untracked)                         docs   30
#                  src/cli.py 40                                                          cli    40
#                  src/engine/core.py 40, src/engine/run.py 30,
#                  src/engine/parse/lexer.py 28, src/engine/parse/grammar.py 20,
#                  src/engine/exec/vm.py 30                                               engine 148
#                  tests/test_cli.py 24, tests/test_new.py 20 (untracked)                tests  44
#                ignored: build/out.txt 25, app.log 5 (30 more, never counted by default)
#                inside .git: .git/needle-note.txt 9 (never searched, even with --no-ignore)
#                In path order the first 50 hits are docs/api.md 12, docs/guide.md 18 and the
#                first 20 of src/cli.py's 40, so the cut falls part-way through a file.
#                The token zz_absent_token appears nowhere (SC-4): it is simply never written.
#
# POSIX sh; prints nothing on success and exits non-zero on any failure.
set -eu

dir="${1:?usage: bounded-read.sh DIR}"
mkdir -p "$dir"
cd "$dir"

# ── plain files ──────────────────────────────────────────────────────────────────────────────────
seq 1 412 | awk '{
  s = "the quick brown fox jumps over the lazy dog and keeps on running"
  printf "line %03d: %s.\n", $1, substr(s, 1, ($1 * 7) % 50 + 3)
}' >big.txt

seq 1 100 | awk '{ printf "small %03d: row %d of the small file\n", $1, $1 }' >small.txt

awk 'BEGIN {
  printf "short line before\n"
  s = ""
  for (i = 0; i < 5000; i++) s = s substr("abcdefghij", i % 10 + 1, 1)
  printf "%s\n", s
  printf "short line after\n"
}' >long.txt

# NULs come from printf repeating its format once per argument (%.0s consumes one, prints nothing).
# shellcheck disable=SC2046 # one word per number, on purpose
{
  printf '\177ELF\002\001\001\000'
  printf '\000%.0s' $(seq 1 2040)
  printf 'BOUNDED_READ_CONTENT_MARKER\n'
} >app.bin
# shellcheck disable=SC2046 # one word per number, on purpose
{
  printf '\211PNG\r\n\032\n'
  printf '\000%.0s' $(seq 1 1000)
  printf 'BOUNDED_READ_CONTENT_MARKER\n'
} >pic.png

printf 'caf\351 au lait\nna\357ve r\351sum\351\nplain ascii line\n' >latin1.txt
printf 'plain line\n\033[31mred text\033[0m here\nanother \033]0;title\007 line\nlast plain line\n' >escapes.txt

# ── the repository ───────────────────────────────────────────────────────────────────────────────
g() {
  git -c user.name="timelike test" -c user.email="test@timelike.invalid" \
    -c init.defaultBranch=main -c commit.gpgsign=false "$@"
}

# hits FILE N — write FILE with N hits, one per line, each hit after a line that does not match, so
# hit line numbers are 2, 4, 6, ... and every line is distinct.
hits() {
  mkdir -p "$(dirname "$1")"
  seq 1 "$2" | awk -v f="$1" '{
    printf "def helper_%d():\n", $1
    printf "    return needle_fn(%d)  # %s hit %d\n", $1, f, $1
  }' >"$1"
}

g init -q repo
cd repo
printf '%s\n' 'build/' '*.log' >.gitignore
printf '%s\n' '# bounded-read fixture' '' 'A repository for the view and search tests.' >README.md

hits docs/api.md 12
hits src/cli.py 40
hits src/engine/core.py 40
hits src/engine/run.py 30
hits src/engine/parse/lexer.py 28
hits src/engine/parse/grammar.py 20
hits src/engine/exec/vm.py 30
hits tests/test_cli.py 24
g add -A
g commit -q -m "bounded-read fixture: first commit"

# Untracked, not ignored: searched like any other file.
hits docs/guide.md 18
hits tests/test_new.py 20

# Ignored by .gitignore: not searched by default.
hits build/out.txt 25
hits app.log 5

# Inside .git: never searched.
hits .git/needle-note.txt 9

# ── check the state the tests rely on, rather than trust the steps above ─────────────────────────
fail() {
  echo "bounded-read: $*" >&2
  exit 1
}

# count_in FILE — matching lines in FILE (grep -c); one hit per line, so this is the hit count.
count_in() { grep -c needle_fn "$1" || true; }

# sum_git_grep [ARG]... — hits git itself finds over tracked and untracked files (git's own ignore
# rules), summed over files.
sum_git_grep() { g grep --untracked -c needle_fn "$@" | awk -F: '{ s += $NF } END { print s + 0 }'; }

cd ..
[ "$(wc -l <big.txt)" -eq 412 ] || fail "big.txt does not have 412 lines"
[ "$(sort -u big.txt | wc -l)" -eq 412 ] || fail "big.txt lines are not distinct"
[ "$(wc -l <small.txt)" -eq 100 ] || fail "small.txt does not have 100 lines"
[ "$(wc -l <long.txt)" -eq 3 ] || fail "long.txt does not have 3 lines"
[ "$(awk 'NR == 2 { print length($0) }' long.txt)" -eq 5000 ] || fail "long.txt line 2 is not 5000 bytes"
[ "$(grep -c 'BOUNDED_READ_CONTENT_MARKER' app.bin)" -eq 1 ] || fail "app.bin lacks its marker"
[ "$(grep -c 'BOUNDED_READ_CONTENT_MARKER' pic.png)" -eq 1 ] || fail "pic.png lacks its marker"
[ "$(od -An -c -N4 app.bin | tr -d ' ')" = '177ELF' ] || fail "app.bin does not start with ELF magic"
[ "$(od -An -c -N4 pic.png | tr -d ' ')" = '211PNG' ] || fail "pic.png does not start with PNG magic"
[ "$(od -An -c -j8 -N1 app.bin | tr -d ' ')" = '\0' ] || fail "app.bin has no NUL in its first bytes"
[ "$(od -An -c -j8 -N1 pic.png | tr -d ' ')" = '\0' ] || fail "pic.png has no NUL in its first bytes"
[ "$(grep -c "$(printf '\033')" escapes.txt)" -eq 2 ] || fail "escapes.txt does not have 2 escape lines"
# A lone 0xE9 byte (latin-1 e-acute) is never valid UTF-8 on its own; 3 of them (bytes, not lines).
[ "$(LC_ALL=C grep -o "$(printf '\351')" latin1.txt | wc -l)" -eq 3 ] || fail "latin1.txt lacks its invalid UTF-8 bytes"

cd repo
for spec in docs/api.md:12 docs/guide.md:18 src/cli.py:40 src/engine/core.py:40 src/engine/run.py:30 \
  src/engine/parse/lexer.py:28 src/engine/parse/grammar.py:20 src/engine/exec/vm.py:30 \
  tests/test_cli.py:24 tests/test_new.py:20 build/out.txt:25 app.log:5 .git/needle-note.txt:9; do
  f="${spec%:*}"
  n="${spec##*:}"
  [ "$(count_in "$f")" -eq "$n" ] || fail "$f has $(count_in "$f") hits, want $n"
  # one hit per line: occurrences equal matching lines
  [ "$(grep -o needle_fn "$f" | wc -l)" -eq "$n" ] || fail "$f has more than one hit on a line"
done

# By plain grep (no ignore rules): outside .git 292, of which 30 are in the ignored paths.
[ "$(grep -r --exclude-dir=.git -o needle_fn . | wc -l)" -eq 292 ] || fail "not 292 hits outside .git"
[ "$(grep -r --exclude-dir=.git --exclude-dir=build --exclude=app.log -o needle_fn . | wc -l)" -eq 262 ] \
  || fail "not 262 hits outside .git and the ignored paths"

# By git's own ignore rules (an independent reading of .gitignore): 262, and the areas.
[ "$(sum_git_grep)" -eq 262 ] || fail "git grep --untracked finds $(sum_git_grep), want 262"
[ "$(sum_git_grep -- src/engine)" -eq 148 ] || fail "src/engine: $(sum_git_grep -- src/engine), want 148"
[ "$(sum_git_grep -- src/cli.py)" -eq 40 ] || fail "src/cli.py: $(sum_git_grep -- src/cli.py), want 40"
[ "$(sum_git_grep -- tests)" -eq 44 ] || fail "tests: $(sum_git_grep -- tests), want 44"
[ "$(sum_git_grep -- docs)" -eq 30 ] || fail "docs: $(sum_git_grep -- docs), want 30"
[ "$(g grep --untracked --no-exclude-standard -c needle_fn | awk -F: '{ s += $NF } END { print s + 0 }')" -eq 292 ] \
  || fail "git grep --no-exclude-standard does not find 292"
g check-ignore -q build/out.txt || fail "build/out.txt is not ignored"
g check-ignore -q app.log || fail "app.log is not ignored"

# Committed and untracked files both carry hits.
[ -n "$(g ls-files src/cli.py)" ] || fail "src/cli.py is not committed"
[ -z "$(g ls-files docs/guide.md tests/test_new.py)" ] || fail "docs/guide.md or tests/test_new.py is tracked"
[ -z "$(g status --porcelain --untracked-files=no)" ] || fail "the tracked files are not clean"

# The absent token is absent everywhere, .git included.
if grep -r -q zz_absent_token .; then
  fail "zz_absent_token appears in the repository"
fi
