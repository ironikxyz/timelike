#!/bin/sh
# Build a real repository for the 005 recover tests (snapshot and undo; tasks.md T001, research R9).
# Runs INSIDE the agent container as the agent user:  sh /tmp/recover-repo-<tag>.sh DIR
#
# Built by git itself (lore cross-stack P005), never by hand-writing .git. The final state has:
#   tracked      src/main.py, src/util/helper.py, README.md, tools/run.sh (0755), secret.cfg (0600),
#                rmsrc.sh (0755, tracked), .gitignore, link-to-readme -> README.md (a symlink)
#   history      two commits on main
#   ignored      build/out.bin (4 KiB of random bytes) and app.log (.gitignore: build/ and *.log)
#   untracked    notes/todo.txt
#   stash        one entry (an edit of src/main.py), so `git stash list` has one line
#   staged       an edit of README.md, added and not committed
#   nested repo  vendor/lib, with its own .git, lib.txt and one commit (untracked in the outer repo)
#   hook         .git/hooks/pre-commit, which writes DIR/../hook-ran if it ever runs. Installed LAST,
#                after every commit the fixture makes, so the marker exists only if something else
#                ran it (SC-3).
# rmsrc.sh deletes the src/ beside it: the wrong directory, deleted by a script (SC-2, Scenario 1).
#
# Only user.name/user.email are set, in each repository's local config. POSIX sh; prints nothing on
# success and exits non-zero on any failure.
set -eu

dir="${1:?usage: recover-repo.sh DIR}"

git init -q -b main "$dir"
cd "$dir"
git config user.name "timelike test"
git config user.email "test@timelike.invalid"

mkdir -p src/util tools
printf '%s\n' 'from util.helper import greet' '' 'print(greet("world"))' >src/main.py
printf '%s\n' 'def greet(name):' '    return "hello " + name' >src/util/helper.py
printf '%s\n' '# recover fixture' '' 'A repository for the snapshot and undo tests.' >README.md
printf '%s\n' '#!/bin/sh' 'echo "tools/run.sh ran"' >tools/run.sh
chmod 0755 tools/run.sh
printf '%s\n' '[fixture]' 'setting = private-to-the-owner' >secret.cfg
chmod 0600 secret.cfg
# shellcheck disable=SC2016 # the script's own text: $0 expands when rmsrc.sh runs, not here
printf '%s\n' '#!/bin/sh' '# Deletes the src/ beside this script.' 'cd "$(dirname "$0")" && rm -rf src' >rmsrc.sh
chmod 0755 rmsrc.sh
printf '%s\n' 'build/' '*.log' >.gitignore
ln -s README.md link-to-readme
git add -A
git commit -q -m "recover fixture: first commit"

printf '%s\n' '' 'Second paragraph.' >>README.md
git add README.md
git commit -q -m "recover fixture: second commit"

# Ignored by git, captured like any other file (spec D-3).
mkdir build
dd if=/dev/urandom of=build/out.bin bs=1024 count=4 2>/dev/null
printf '%s\n' 'log line 1' 'log line 2' >app.log

# Untracked.
mkdir notes
printf '%s\n' 'restore the wrong directory' >notes/todo.txt

# A nested repository: its working files are captured, its .git never is (spec D-4).
git init -q -b main vendor/lib
git -C vendor/lib config user.name "timelike test"
git -C vendor/lib config user.email "test@timelike.invalid"
printf '%s\n' 'vendored library' >vendor/lib/lib.txt
git -C vendor/lib add lib.txt
git -C vendor/lib commit -q -m "lib: first commit"

# A stash (an edit of a tracked file), then a staged change, so the staged change is the final state.
printf '%s\n' '# an edit that was stashed' >>src/main.py
git stash push -q -m "recover fixture stash"
printf '%s\n' 'Staged line.' >>README.md
git add README.md

# The repository's own hook, last: no commit is made after this.
marker="$(cd .. && pwd)/hook-ran"
printf '%s\n' '#!/bin/sh' ": > '${marker}'" >.git/hooks/pre-commit
chmod 0755 .git/hooks/pre-commit

# Check the state the tests rely on, rather than trust the steps above.
[ "$(git stash list | wc -l)" -eq 1 ] || { echo "recover-repo: expected one stash entry" >&2; exit 1; }
if git diff --cached --quiet; then
  echo "recover-repo: expected a staged change" >&2
  exit 1
fi
git check-ignore -q build/out.bin || { echo "recover-repo: build/out.bin is not ignored" >&2; exit 1; }
git check-ignore -q app.log || { echo "recover-repo: app.log is not ignored" >&2; exit 1; }
[ -z "$(git ls-files notes/todo.txt)" ] || { echo "recover-repo: notes/todo.txt is tracked" >&2; exit 1; }
git ls-files --error-unmatch src/main.py rmsrc.sh link-to-readme >/dev/null
[ -d vendor/lib/.git ] || { echo "recover-repo: vendor/lib has no .git" >&2; exit 1; }
[ ! -e "$marker" ] || { echo "recover-repo: the hook marker exists already" >&2; exit 1; }
