#!/bin/sh
# Prepare a git repository in a given state for SC-1 (tests/e2e) and the SC-7 demo (scripts/demo.sh).
# Runs INSIDE the agent container as the agent user:  sh /tmp/sc1-repo.sh DIR STATE
#
#   log     more than one screen of history (60 commits)            → then: git log
#   diff    history plus a 120-line unstaged change                  → then: git diff
#   commit  history plus a staged change                             → then: git commit   (no -m)
#   rebase  a rebase stopped on a conflict, resolved and staged      → then: git rebase --continue
#
# Common failures (slice 1, natural intensity; modify.md F005), each a state a real user meets:
#   merge     main and topic diverged, no conflict                   → then: git merge topic
#   conflict  main and topic diverged, conflicting in conflict.txt   → then: git merge topic
#   merging   a merge stopped on that conflict, resolved and staged  → then: git commit   (no -m)
#   (`log` serves git rebase -i and git commit --amend is run on `commit`; `diff` serves git add -p.)
#
# Only user.name/user.email are set, in the repository's local config. Nothing here sets an editor,
# pager or hook: those defaults are what the tests are about, and a fixture that set them would hide
# the thing being tested. Setup commands pass -m and never need an editor. POSIX sh on purpose: the
# fixture must not depend on bash startup behaviour either.
set -eu

dir="$1"
state="$2"

git init -q -b main "$dir"
cd "$dir"
git config user.name "timelike test"
git config user.email "test@timelike.invalid"

i=1
while [ "$i" -le 60 ]; do
  echo "history line $i" >>history.txt
  git add history.txt
  git commit -q -m "history commit $i"
  i=$((i + 1))
done

# diverge CONFLICT_CONTENT — topic and main each add one commit; when both sides write conflict.txt
# with different content, merging topic into main conflicts. Leaves main checked out.
diverge() {
  git checkout -q -b topic
  echo "topic side" >conflict.txt
  git add conflict.txt
  git commit -q -m "topic: side change"
  git checkout -q main
  echo "$1" >"$2"
  git add "$2"
  git commit -q -m "main: side change"
}

case "$state" in
  log) ;;
  diff)
    i=1
    while [ "$i" -le 120 ]; do
      echo "extra line $i" >>history.txt
      i=$((i + 1))
    done
    ;;
  commit)
    echo "staged content" >staged.txt
    git add staged.txt
    ;;
  rebase)
    git checkout -q -b topic
    echo "topic side" >conflict.txt
    git add conflict.txt
    git commit -q -m "topic: the message rebase must keep"
    git checkout -q main
    echo "main side" >conflict.txt
    git add conflict.txt
    git commit -q -m "main: conflicting change"
    git checkout -q topic
    if git rebase main >/dev/null 2>&1; then
      echo "sc1-repo: rebase did not stop on the conflict" >&2
      exit 1
    fi
    if [ ! -d .git/rebase-merge ] && [ ! -d .git/rebase-apply ]; then
      echo "sc1-repo: no rebase in progress after the conflict" >&2
      exit 1
    fi
    echo "resolved" >conflict.txt
    git add conflict.txt
    ;;
  merge)
    diverge "main side" main.txt
    ;;
  conflict)
    diverge "main side" conflict.txt
    ;;
  merging)
    diverge "main side" conflict.txt
    if git merge topic >/dev/null 2>&1; then
      echo "sc1-repo: merge did not stop on the conflict" >&2
      exit 1
    fi
    if [ ! -f .git/MERGE_HEAD ]; then
      echo "sc1-repo: no merge in progress after the conflict" >&2
      exit 1
    fi
    echo "resolved" >conflict.txt
    git add conflict.txt
    ;;
  *)
    echo "sc1-repo: unknown state '$state' (want log|diff|commit|rebase|merge|conflict|merging)" >&2
    exit 2
    ;;
esac
echo "sc1-repo: $dir ready for $state"
