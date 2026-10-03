#!/usr/bin/env bats
# SC-1 — "With the harness's non-interactive invocation, git log, git diff, git commit without a
# message, and git rebase --continue each exit within 20 seconds without opening a pager or editor."
# (tasks.md T015; spec FR-2; research R2, R8.)
#
# Every command is run from OUTSIDE the container (lore cross-stack P005) in each invocation style
# (bash -c, bash -lc, bash -ic) and each terminal mode (notty = the harness's own invocation; tty =
# docker exec -t; pty = util-linux script inside the container — see helpers.bash). A terminal is
# what exposes a pager or editor: without one, git would not page anyway, so notty alone proves little.
#
# Each test asserts, reading the artefacts rather than a success message (lore cross-stack P004):
#   - measured wall time < 20 s, and not a timeout (rc 124 = the runner killed a hang after 30 s)
#   - the exact exit status
#   - the repository state the command must leave (HEAD unchanged; rebase finished, message kept)
#   - no pager or editor process left in the container (process table read directly)
# Not asserted: a pager or editor that starts and exits again within the run. A pager on a tty with
# more than one screen of output (log, diff) cannot exit by itself, so it would hang and show as 124.
#
# Common failures (slice 1, natural intensity; modify.md F005; tasks.md T053). The same four defaults
# (R2) must also cover the neighbouring git paths a real user meets, each of which opens an editor, a
# sequence editor or a pager in an ordinary shell (each confirmed locally to hang, rc 124, under a pty
# with the defaults removed):
#   git commit --amend        commit-message editor, pre-filled         → rc 0, message kept
#   git merge (diverged)      merge-message editor (GIT_MERGE_AUTOEDIT)  → rc 0, merge commit made
#   git merge (conflicting)   must stop at once, not wait                → rc 1, merge left in progress
#   git commit (mid-merge)    editor over the prepared MERGE_MSG         → rc 0, merge concluded
#   git rebase -i             sequence editor (the todo list)            → rc 0, HEAD unchanged
#   git log --help            man and its pager                          → concludes, no pager
#   git add -p                reads its answers from stdin               → rc 0, nothing staged
# Cells: bash -c and bash -lc (the harness's two invocations, spec Assumption 1), in `tty` mode — the
# terminal that turns an editor or pager into a hang (R8). Whether the defaults reach each style and
# mode is SC-2's matrix and the happy path above; these cells prove the defaults are sufficient for
# another code path, which does not vary by style once the defaults are present, so the full 3 × 3
# would add runtime and no information. git add -p is the exception: it reads stdin, not the
# terminal, so under `docker exec -t` it would block on any build (as `cat` would); a stdin reader is
# bounded by the harness's stdin being /dev/null (R5), so it runs in `notty` — the harness's own mode.

load helpers

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/sc1-repo.sh" /tmp/sc1-repo.sh 0755
}

setup() {
  WORK=""
  REPO_DIR=""
}

teardown() {
  kill_strays
  container_rm "$WORK"
}

# prepare STATE — a fresh repository in the given state (fixtures/sc1-repo.sh), in a new temp dir.
prepare() {
  WORK="$(container_tmpdir sc1)"
  REPO_DIR="${WORK}/repo"
  exec_plain sh /tmp/sc1-repo.sh "$REPO_DIR" "$1" >/dev/null
}

# assert_line_matching ERE — some line of $output matches, ignoring ANSI colour codes: colour is
# SC-2's criterion, and SC-1 must not fail (or pass) because of it.
assert_line_matching() {
  local line plain esc=$'\e'
  for line in "${lines[@]}"; do
    # shellcheck disable=SC2001 # a regex (CSI sequences), which ${var//} cannot express
    plain="$(sed "s/${esc}\[[0-9;]*[A-Za-z]//g" <<<"$line")"
    [[ "$plain" =~ $1 ]] && return 0
  done
  printf 'no line matches /%s/; output:\n%s\n' "$1" "$output" >&2
  return 1
}

check_git_log() {
  prepare log
  run_in "$1" "$2" "cd '${REPO_DIR}' && git log"
  assert_within 20
  assert_status 0
  # The oldest commit is the last thing git log prints: the whole log reached us, not a pager's page.
  assert_line_matching '^    history commit 60$'
  assert_line_matching '^    history commit 1$'
  assert_no_pager_or_editor
}

check_git_diff() {
  prepare diff
  run_in "$1" "$2" "cd '${REPO_DIR}' && git diff"
  assert_within 20
  assert_status 0
  assert_line_matching '^diff --git a/history.txt b/history.txt$'
  assert_line_matching '^\+extra line 120$'
  assert_no_pager_or_editor
}

check_git_commit_without_message() {
  prepare commit
  run_in "$1" "$2" "cd '${REPO_DIR}' && git commit"
  assert_within 20
  assert_status 1
  assert_output_has "Aborting commit due to empty commit message"
  assert_no_pager_or_editor
  # Artefact: no commit was made, and the change is still staged.
  run exec_plain git -C "$REPO_DIR" rev-list --count HEAD
  [[ "$output" == 60 ]] || { echo "HEAD moved: $output commits, expected 60" >&2; return 1; }
  run exec_plain git -C "$REPO_DIR" diff --cached --name-only
  [[ "$output" == staged.txt ]] || { echo "staged change lost: '$output'" >&2; return 1; }
}

check_git_rebase_continue() {
  prepare rebase
  run_in "$1" "$2" "cd '${REPO_DIR}' && git rebase --continue"
  assert_within 20
  assert_status 0
  assert_no_pager_or_editor
  # Artefact: the rebase is finished and the commit kept its existing message.
  run exec_plain git -C "$REPO_DIR" log -1 --format=%s
  [[ "$output" == "topic: the message rebase must keep" ]] || { echo "message not kept: '$output'" >&2; return 1; }
  run exec_plain test -d "${REPO_DIR}/.git/rebase-merge" -o -d "${REPO_DIR}/.git/rebase-apply"
  [[ "$status" -ne 0 ]] || { echo "a rebase is still in progress" >&2; return 1; }
  run exec_plain git -C "$REPO_DIR" rev-list --count HEAD
  [[ "$output" == 62 ]] || { echo "expected 62 commits after the rebase, got $output" >&2; return 1; }
}

# --- common failures (slice 1) ---

check_git_commit_amend() {
  prepare commit
  run_in "$1" "$2" "cd '${REPO_DIR}' && git commit --amend"
  assert_within 20
  assert_status 0
  assert_no_pager_or_editor
  # Artefact: the staged file was folded into the last commit, whose message was kept (no new commit).
  run exec_plain git -C "$REPO_DIR" rev-list --count HEAD
  [[ "$output" == 60 ]] || { echo "expected 60 commits after --amend, got $output" >&2; return 1; }
  run exec_plain git -C "$REPO_DIR" log -1 --format=%s
  [[ "$output" == "history commit 60" ]] || { echo "message not kept: '$output'" >&2; return 1; }
  run exec_plain git -C "$REPO_DIR" show --name-only --format= HEAD
  [[ "$output" == *staged.txt* ]] || { echo "staged.txt not in the amended commit: '$output'" >&2; return 1; }
  run exec_plain git -C "$REPO_DIR" diff --cached --name-only
  [[ -z "$output" ]] || { echo "changes still staged after --amend: '$output'" >&2; return 1; }
}

check_git_merge_diverged() {
  prepare merge
  run_in "$1" "$2" "cd '${REPO_DIR}' && git merge topic"
  assert_within 20
  assert_status 0
  assert_no_pager_or_editor
  # Artefact: a real merge commit (two parents) with git's default message: no editor was consulted.
  run exec_plain git -C "$REPO_DIR" log -1 --format=%s
  [[ "$output" == "Merge branch 'topic'" ]] || { echo "unexpected merge message: '$output'" >&2; return 1; }
  run exec_plain git -C "$REPO_DIR" rev-list --count HEAD
  [[ "$output" == 63 ]] || { echo "expected 63 commits after the merge, got $output" >&2; return 1; }
  run exec_plain git -C "$REPO_DIR" rev-parse -q --verify HEAD^2
  [[ "$status" -eq 0 ]] || { echo "HEAD is not a merge commit (no second parent)" >&2; return 1; }
}

check_git_merge_conflict() {
  prepare conflict
  run_in "$1" "$2" "cd '${REPO_DIR}' && git merge topic"
  assert_within 20
  assert_status 1
  assert_output_has "Automatic merge failed"
  assert_no_pager_or_editor
  # Artefact: nothing was committed, and the merge is left in progress for the agent to resolve.
  run exec_plain git -C "$REPO_DIR" rev-list --count HEAD
  [[ "$output" == 61 ]] || { echo "HEAD moved: $output commits, expected 61" >&2; return 1; }
  run exec_plain test -f "${REPO_DIR}/.git/MERGE_HEAD"
  [[ "$status" -eq 0 ]] || { echo "no merge in progress (MERGE_HEAD absent)" >&2; return 1; }
}

check_git_commit_mid_merge() {
  prepare merging
  run_in "$1" "$2" "cd '${REPO_DIR}' && git commit"
  assert_within 20
  assert_status 0
  assert_no_pager_or_editor
  # Artefact: the merge concluded with its prepared message, and no merge is in progress any more.
  run exec_plain git -C "$REPO_DIR" log -1 --format=%s
  [[ "$output" == "Merge branch 'topic'" ]] || { echo "prepared merge message not kept: '$output'" >&2; return 1; }
  run exec_plain git -C "$REPO_DIR" rev-parse -q --verify HEAD^2
  [[ "$status" -eq 0 ]] || { echo "HEAD is not a merge commit (no second parent)" >&2; return 1; }
  run exec_plain test -f "${REPO_DIR}/.git/MERGE_HEAD"
  [[ "$status" -ne 0 ]] || { echo "a merge is still in progress" >&2; return 1; }
}

check_git_rebase_interactive() {
  prepare log
  local before
  before="$(exec_plain git -C "$REPO_DIR" rev-parse HEAD)"
  run_in "$1" "$2" "cd '${REPO_DIR}' && git rebase -i HEAD~3"
  assert_within 20
  assert_status 0
  assert_no_pager_or_editor
  # Artefact: the unedited todo list picked every commit unchanged, so HEAD is where it was.
  run exec_plain git -C "$REPO_DIR" rev-parse HEAD
  [[ "$output" == "$before" ]] || { echo "HEAD moved from $before to $output" >&2; return 1; }
  run exec_plain test -d "${REPO_DIR}/.git/rebase-merge" -o -d "${REPO_DIR}/.git/rebase-apply"
  [[ "$status" -ne 0 ]] || { echo "a rebase is still in progress" >&2; return 1; }
}

# The image ships no man (debian slim, --no-install-recommends), so git's help viewer fails at once:
# rc 128, "no man viewer handled the request" (confirmed locally with man off PATH). If man is ever
# installed, MANPAGER=cat (R5) must let it print and exit 0. The test reads which case applies, in
# the same run, and asserts that case exactly.
check_git_help() {
  # shellcheck disable=SC2016 # expanded in the container
  run_in "$1" "$2" 'cd / || exit 97; if command -v man >/dev/null; then echo man=present; else echo man=absent; fi; git log --help; echo "help-rc=$?"'
  assert_within 20
  assert_status 0
  assert_no_pager_or_editor
  case "$(value_of man)" in
    absent)
      assert_value help-rc 128
      assert_output_has "no man viewer handled the request"
      ;;
    present)
      assert_value help-rc 0
      assert_line_matching 'git-log'
      ;;
    *) printf 'could not read whether man is present; output:\n%s\n' "$output" >&2; return 1 ;;
  esac
}

check_git_add_patch() {
  prepare diff
  run_in "$1" "$2" "cd '${REPO_DIR}' && git add -p"
  assert_within 20
  assert_status 0
  # git reached the question and read end-of-input instead of waiting for an answer.
  assert_output_has "Stage this hunk"
  assert_no_pager_or_editor
  # Artefact: no answer, so nothing was staged and the change is still in the working tree.
  run exec_plain git -C "$REPO_DIR" diff --cached --name-only
  [[ -z "$output" ]] || { echo "git add -p staged '$output' without an answer" >&2; return 1; }
  run exec_plain git -C "$REPO_DIR" diff --name-only
  [[ "$output" == history.txt ]] || { echo "working-tree change lost: '$output'" >&2; return 1; }
}

# --- git log ---
@test "SC-1 git log exits within 20 seconds without a pager [bash -c, notty]" { check_git_log c notty; }
@test "SC-1 git log exits within 20 seconds without a pager [bash -c, tty]" { check_git_log c tty; }
@test "SC-1 git log exits within 20 seconds without a pager [bash -c, pty]" { check_git_log c pty; }
@test "SC-1 git log exits within 20 seconds without a pager [bash -lc, notty]" { check_git_log lc notty; }
@test "SC-1 git log exits within 20 seconds without a pager [bash -lc, tty]" { check_git_log lc tty; }
@test "SC-1 git log exits within 20 seconds without a pager [bash -lc, pty]" { check_git_log lc pty; }
@test "SC-1 git log exits within 20 seconds without a pager [bash -ic, notty]" { check_git_log ic notty; }
@test "SC-1 git log exits within 20 seconds without a pager [bash -ic, tty]" { check_git_log ic tty; }
@test "SC-1 git log exits within 20 seconds without a pager [bash -ic, pty]" { check_git_log ic pty; }

# --- git diff ---
@test "SC-1 git diff exits within 20 seconds without a pager [bash -c, notty]" { check_git_diff c notty; }
@test "SC-1 git diff exits within 20 seconds without a pager [bash -c, tty]" { check_git_diff c tty; }
@test "SC-1 git diff exits within 20 seconds without a pager [bash -c, pty]" { check_git_diff c pty; }
@test "SC-1 git diff exits within 20 seconds without a pager [bash -lc, notty]" { check_git_diff lc notty; }
@test "SC-1 git diff exits within 20 seconds without a pager [bash -lc, tty]" { check_git_diff lc tty; }
@test "SC-1 git diff exits within 20 seconds without a pager [bash -lc, pty]" { check_git_diff lc pty; }
@test "SC-1 git diff exits within 20 seconds without a pager [bash -ic, notty]" { check_git_diff ic notty; }
@test "SC-1 git diff exits within 20 seconds without a pager [bash -ic, tty]" { check_git_diff ic tty; }
@test "SC-1 git diff exits within 20 seconds without a pager [bash -ic, pty]" { check_git_diff ic pty; }

# --- git commit without a message ---
@test "SC-1 git commit without a message exits within 20 seconds without an editor [bash -c, notty]" { check_git_commit_without_message c notty; }
@test "SC-1 git commit without a message exits within 20 seconds without an editor [bash -c, tty]" { check_git_commit_without_message c tty; }
@test "SC-1 git commit without a message exits within 20 seconds without an editor [bash -c, pty]" { check_git_commit_without_message c pty; }
@test "SC-1 git commit without a message exits within 20 seconds without an editor [bash -lc, notty]" { check_git_commit_without_message lc notty; }
@test "SC-1 git commit without a message exits within 20 seconds without an editor [bash -lc, tty]" { check_git_commit_without_message lc tty; }
@test "SC-1 git commit without a message exits within 20 seconds without an editor [bash -lc, pty]" { check_git_commit_without_message lc pty; }
@test "SC-1 git commit without a message exits within 20 seconds without an editor [bash -ic, notty]" { check_git_commit_without_message ic notty; }
@test "SC-1 git commit without a message exits within 20 seconds without an editor [bash -ic, tty]" { check_git_commit_without_message ic tty; }
@test "SC-1 git commit without a message exits within 20 seconds without an editor [bash -ic, pty]" { check_git_commit_without_message ic pty; }

# --- git rebase --continue ---
@test "SC-1 git rebase --continue exits within 20 seconds without an editor [bash -c, notty]" { check_git_rebase_continue c notty; }
@test "SC-1 git rebase --continue exits within 20 seconds without an editor [bash -c, tty]" { check_git_rebase_continue c tty; }
@test "SC-1 git rebase --continue exits within 20 seconds without an editor [bash -c, pty]" { check_git_rebase_continue c pty; }
@test "SC-1 git rebase --continue exits within 20 seconds without an editor [bash -lc, notty]" { check_git_rebase_continue lc notty; }
@test "SC-1 git rebase --continue exits within 20 seconds without an editor [bash -lc, tty]" { check_git_rebase_continue lc tty; }
@test "SC-1 git rebase --continue exits within 20 seconds without an editor [bash -lc, pty]" { check_git_rebase_continue lc pty; }
@test "SC-1 git rebase --continue exits within 20 seconds without an editor [bash -ic, notty]" { check_git_rebase_continue ic notty; }
@test "SC-1 git rebase --continue exits within 20 seconds without an editor [bash -ic, tty]" { check_git_rebase_continue ic tty; }
@test "SC-1 git rebase --continue exits within 20 seconds without an editor [bash -ic, pty]" { check_git_rebase_continue ic pty; }

# --- common failures (slice 1): neighbouring git paths that open an editor, pager or prompt ---
@test "SC-1 git commit --amend exits within 20 seconds without an editor, message kept [bash -c, tty]" { check_git_commit_amend c tty; }
@test "SC-1 git commit --amend exits within 20 seconds without an editor, message kept [bash -lc, tty]" { check_git_commit_amend lc tty; }
@test "SC-1 git merge of diverged branches exits within 20 seconds without a merge-message editor [bash -c, tty]" { check_git_merge_diverged c tty; }
@test "SC-1 git merge of diverged branches exits within 20 seconds without a merge-message editor [bash -lc, tty]" { check_git_merge_diverged lc tty; }
@test "SC-1 git merge with a conflict exits non-zero within 20 seconds, merge left in progress [bash -c, tty]" { check_git_merge_conflict c tty; }
@test "SC-1 git merge with a conflict exits non-zero within 20 seconds, merge left in progress [bash -lc, tty]" { check_git_merge_conflict lc tty; }
@test "SC-1 git commit after a resolved merge conflict exits within 20 seconds without an editor [bash -c, tty]" { check_git_commit_mid_merge c tty; }
@test "SC-1 git commit after a resolved merge conflict exits within 20 seconds without an editor [bash -lc, tty]" { check_git_commit_mid_merge lc tty; }
@test "SC-1 git rebase -i exits within 20 seconds without a sequence editor [bash -c, tty]" { check_git_rebase_interactive c tty; }
@test "SC-1 git rebase -i exits within 20 seconds without a sequence editor [bash -lc, tty]" { check_git_rebase_interactive lc tty; }
@test "SC-1 git log --help exits within 20 seconds without a pager [bash -c, tty]" { check_git_help c tty; }
@test "SC-1 git log --help exits within 20 seconds without a pager [bash -lc, tty]" { check_git_help lc tty; }
@test "SC-1 git add -p with no input exits within 20 seconds, nothing staged [bash -c, notty]" { check_git_add_patch c notty; }
@test "SC-1 git add -p with no input exits within 20 seconds, nothing staged [bash -lc, notty]" { check_git_add_patch lc notty; }
