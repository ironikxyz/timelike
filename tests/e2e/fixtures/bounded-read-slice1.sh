#!/bin/sh
# Build the files for the 006 slice-1 tests (view DIR, view --anchors, the carried items; tasks.md
# T018). Runs INSIDE the agent container as the agent user:
#
#   sh /tmp/bounded-read-slice1-<tag>.sh KIND DIR
#
# Content is made with printf, git and the image's Python, never with view or search (lore
# cross-stack P005), and every count the tests rely on is checked at the end with find, grep, wc and
# git, so a fixture that drifts fails here, at build time, not as a confusing test failure.
#
#   overview DIR   DIR/repo, a real git repository (SC-6):
#                    .gitignore      node_modules/ and *.log
#                    README.md, src/main.py, src/util/io.py, docs/guide.md      committed
#                    debug.log                                                   ignored by *.log
#                    node_modules/   100 package directories pkg-000..pkg-099, each holding
#                                    index.js and lib/ with 99 files: 10,000 files, 200 dirs,
#                                    ignored by .gitignore, never committed
#                    .git/           git's own
#   anchors DIR    DIR/anchors.txt, 60 lines ending in a newline (SC-7):
#                    line 10  "same text here" ending in CRLF; line 11 the same text ending in LF
#                    line 20  305 bytes of ASCII (longer than COLUMNS' default 200)
#                    line 30  a lone 0xE9 byte (latin-1 e-acute; never valid UTF-8 on its own)
#                    lines 45, 46  empty
#                    the other 54 lines "anchor line NN: <words>", distinct
#   plural DIR     DIR/one/one.txt   the token zz_plural_token once        (FR-36)
#                  DIR/two/a.txt     the token twice; DIR/two/b.txt without it
#   corpus DIR     DIR/corpus/part-1.txt .. part-8.txt, 5 MiB each (40 MiB), plain ASCII text with
#                  the token needle_speed_token on 40 lines in all, 5 per file   (FR-37)
#
# POSIX sh; prints nothing on success and exits non-zero on any failure.
set -eu

kind="${1:?usage: bounded-read-slice1.sh overview|anchors|plural|corpus DIR}"
dir="${2:?usage: bounded-read-slice1.sh overview|anchors|plural|corpus DIR}"
PY=/opt/timelike/python/bin/python3

fail() {
  echo "bounded-read-slice1 ${kind}: $*" >&2
  exit 1
}

g() {
  git -c user.name="timelike test" -c user.email="test@timelike.invalid" \
    -c init.defaultBranch=main -c commit.gpgsign=false "$@"
}

mkdir -p "$dir"
cd "$dir"

case "$kind" in
overview)
  g init -q repo
  cd repo
  printf '%s\n' 'node_modules/' '*.log' >.gitignore
  printf '%s\n' '# overview fixture' '' 'A repository for the directory overview test.' >README.md
  mkdir -p src/util docs
  printf '%s\n' 'from util.io import read' '' 'print(read("README.md"))' >src/main.py
  printf '%s\n' 'def read(path):' '    with open(path) as f:' '        return f.read()' >src/util/io.py
  printf '%s\n' '# guide' '' 'How to use the fixture.' >docs/guide.md
  printf '%s\n' 'debug output, ignored' >debug.log
  "$PY" -I -c '
import os
for p in range(100):
    d = "node_modules/pkg-%03d" % p
    os.makedirs(d + "/lib")
    with open(d + "/index.js", "w") as f:
        f.write("module.exports = require(\"./lib/f00.js\");\n")
    for i in range(99):
        with open("%s/lib/f%02d.js" % (d, i), "w") as f:
            f.write("exports.v%d = %d;\n" % (i, p * 100 + i))
'
  g add -A
  g commit -q -m "overview fixture: first commit"

  [ "$(find node_modules -type f | wc -l)" -eq 10000 ] || fail "node_modules does not hold 10000 files"
  [ "$(find node_modules -mindepth 1 -type d | wc -l)" -eq 200 ] || fail "node_modules does not hold 200 dirs"
  [ "$(find node_modules -mindepth 1 -maxdepth 1 | wc -l)" -eq 100 ] || fail "node_modules does not hold 100 entries"
  [ -z "$(find node_modules ! -type f ! -type d)" ] || fail "node_modules holds something other than files and dirs"
  [ -z "$(find . -path ./.git -prune -o -type l -print)" ] || fail "the repository holds a symlink"
  g check-ignore -q node_modules/pkg-000/index.js || fail "node_modules is not ignored"
  g check-ignore -q debug.log || fail "debug.log is not ignored"
  if g check-ignore -q src/main.py; then fail "src/main.py is ignored"; fi
  [ -z "$(g ls-files node_modules debug.log)" ] || fail "node_modules or debug.log is tracked"
  [ "$(g ls-files | wc -l)" -eq 5 ] || fail "not 5 tracked files"
  [ -z "$(g status --porcelain)" ] || fail "the work tree is not clean"
  ;;

anchors)
  "$PY" -I -c '
lines = []
for n in range(1, 61):
    if n in (10, 11):
        lines.append(b"same text here" + (b"\r\n" if n == 10 else b"\n"))
    elif n == 20:
        lines.append(b"long line 20: " + bytes((ord("a") + i % 26) for i in range(291)) + b"\n")
    elif n == 30:
        lines.append(b"line 30: caf\xe9 au lait\n")
    elif n in (45, 46):
        lines.append(b"\n")
    else:
        lines.append(b"anchor line %02d: %s\n" % (n, b" ".join([b"word"] * (n % 7 + 1))))
with open("anchors.txt", "wb") as f:
    f.write(b"".join(lines))
'
  [ "$(wc -l <anchors.txt)" -eq 60 ] || fail "anchors.txt does not have 60 lines"
  [ "$(tail -c 1 anchors.txt | od -An -c | tr -d ' ')" = '\n' ] || fail "anchors.txt does not end in a newline"
  [ "$(grep -c "$(printf '\r')" anchors.txt)" -eq 1 ] || fail "anchors.txt does not have exactly one CR"
  [ "$(awk 'NR == 10' anchors.txt)" = "$(printf 'same text here\r')" ] || fail "line 10 is not the CRLF line"
  [ "$(awk 'NR == 11' anchors.txt)" = "same text here" ] || fail "line 11 is not the LF copy"
  [ "$(LC_ALL=C awk 'NR == 20 { print length($0) }' anchors.txt)" -eq 305 ] || fail "line 20 is not 305 bytes"
  [ "$(LC_ALL=C grep -c "$(printf '\351')" anchors.txt)" -eq 1 ] || fail "anchors.txt lacks its one invalid byte"
  [ "$(LC_ALL=C grep -n "$(printf '\351')" anchors.txt | cut -d: -f1)" -eq 30 ] || fail "the invalid byte is not on line 30"
  [ "$(grep -c '^$' anchors.txt)" -eq 2 ] || fail "anchors.txt does not have 2 empty lines"
  [ "$(grep '^anchor line' anchors.txt | sort -u | wc -l)" -eq 54 ] || fail "the plain lines are not 54 distinct"
  ;;

plural)
  mkdir -p one two
  printf '%s\n' 'first line' 'the zz_plural_token is here' 'last line' >one/one.txt
  printf '%s\n' 'zz_plural_token one' 'nothing' 'zz_plural_token two' >two/a.txt
  printf '%s\n' 'nothing to find here' >two/b.txt
  [ "$(find one -type f | wc -l)" -eq 1 ] || fail "one/ does not hold exactly 1 file"
  [ "$(find two -type f | wc -l)" -eq 2 ] || fail "two/ does not hold exactly 2 files"
  [ "$(grep -r -o zz_plural_token one | wc -l)" -eq 1 ] || fail "one/ does not hold exactly 1 match"
  [ "$(grep -r -o zz_plural_token two | wc -l)" -eq 2 ] || fail "two/ does not hold exactly 2 matches"
  [ "$(grep -r -l zz_plural_token two | wc -l)" -eq 1 ] || fail "two/'s matches are not in exactly 1 file"
  ;;

corpus)
  mkdir -p corpus
  "$PY" -I -c '
words = b"alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike".split()
target = 5 * 1024 * 1024
for part in range(1, 9):
    out, size, n, hits = [], 0, 0, 0
    while size < target:
        n += 1
        if n % 10000 == 0 and hits < 5:
            line = b"row %07d: needle_speed_token found here\n" % n
            hits += 1
        else:
            line = b"row %07d: %s %s %s %s value=%d\n" % (
                n, words[n % 13], words[(n * 7) % 13], words[(n * 11) % 13], words[(n * 3) % 13], n * 31 % 9973)
        out.append(line)
        size += len(line)
    data = b"".join(out)[:target]
    data = data[: data.rindex(b"\n") + 1]
    with open("corpus/part-%d.txt" % part, "wb") as f:
        f.write(data)
'
  [ "$(find corpus -type f | wc -l)" -eq 8 ] || fail "corpus does not hold 8 files"
  [ "$(cat corpus/*.txt | wc -c)" -ge $((40 * 1024 * 1024 - 8 * 100)) ] || fail "corpus is smaller than 40 MiB"
  [ "$(grep -r -o needle_speed_token corpus | wc -l)" -eq 40 ] || fail "corpus does not hold exactly 40 hits"
  for f in corpus/*.txt; do
    [ "$(grep -c needle_speed_token "$f")" -eq 5 ] || fail "$f does not hold 5 hits"
  done
  ;;

*)
  fail "unknown kind (want overview|anchors|plural|corpus)"
  ;;
esac
