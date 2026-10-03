"""catalog — the slice-0 task catalog: four git tasks where timelike's defaults can change the outcome.

Each task is identical in both images (RB4). Its setup and check are bash, run in the task directory
outside the counted run; its policy is fake-agent data interpreted by `fakeagent.next_step`, which
cannot see which image it is in. The tasks were chosen *because* timelike differs there (RB11 item 2),
so the catalog shows where a difference can occur, not how often one does.

Rules every script here obeys, and tests/unit/test_bench_catalog.py enforces:
- Only what **both** images contain (RB1): bash, coreutils, git, and Debian's Essential tools (sed,
  grep). No interpreter, no build tool, no process tools, no network — a task that needed one would
  rig the result, so `prerequisites` declares the OS packages and slice 0 declares only git.
- The identity is repo-local. Neither image sets one, and a global identity would be a difference
  between the bench's own setup and the environment under test.
- Setup commits carry fixed dates, so the same setup gives the same object ids in both images.
- Checks judge git state and files, never the agent's output (FR-13's spirit, applied per task).
- Hooks are `#!/bin/sh` and executable, and are installed after the setup's own commits, so the setup
  never runs its own hook.

`version` is bumped whenever a task's setup, policy or check changes; it is recorded in every trace.
`expected` is research RB4's prediction, verbatim in substance. It is shown in `--verbose` and never
used for scoring.

Stdlib only (H5). Nothing here runs inside an environment under test.
"""

from __future__ import annotations

from dataclasses import dataclass

from benchlib.fakeagent import DONE, Policy, Step, give_up


@dataclass(frozen=True)
class Task:
    """One catalog task. See data-model.md § Task."""

    id: str
    version: int
    capability: str
    goal: str
    prerequisites: tuple[str, ...]
    setup: str
    policy: Policy
    check: str
    expected: str
    # What differs between the two images for this task: a fact about the environments, never a claim
    # about the outcome. Printed under the task in every report (send …-080659, F002).
    difference: str = ""
    # Interpretations written with the task, keyed "<environment>:<ending kind>". The report prints one
    # only when that arm actually ended that way, so a note can never describe a run that didn't happen.
    notes: tuple[tuple[str, str], ...] = ()


# Shared by every setup: strict mode, a repo on `main`, a repo-local identity, fixed commit dates.
_PRELUDE = """\
set -eu
export GIT_AUTHOR_DATE='2026-01-01T00:00:00+0000' GIT_COMMITTER_DATE='2026-01-01T00:00:00+0000'
git init -q -b main
git config user.name 'Bench Setup'
git config user.email 'bench@example.invalid'
"""

_COMMIT_MSG = "bench: update f"

# Shared by every check: a failing check says why in one plain line on stderr, which the runner puts in
# the trace's ending reason and the report shows to its reader (send …-080659, F003). The commands' own
# stderr goes to /dev/null, so git's messages can never stand in front of the reason.
_CHECK_PRELUDE = """\
set -u
exec 3>&2 2>/dev/null
fail() { printf '%s\\n' "$1" >&3; exit 1; }
"""


# --- git-inspect: pager defaults (the control) ---------------------------------------------------

_INSPECT = Task(
    id="git-inspect",
    version=2,
    capability="Pager defaults (control)",
    goal="Write the last five log entries and the unstaged diff to out/.",
    prerequisites=("git",),
    setup=_PRELUDE
    + """\
for n in 1 2 3 4 5 6; do
  printf 'line %s\\n' "$n" >> f
  git add f
  git commit -q -m "commit $n"
done
printf 'unstaged change\\n' >> f
mkdir out
""",
    policy=Policy(
        start="log",
        steps=(
            Step(
                "log",
                "git log -n 5 > out/log.txt",
                on_ok="diff",
                on_fail=give_up("git log failed"),
                on_hang=give_up("git log hung"),
            ),
            Step(
                "diff",
                "git diff > out/diff.txt",
                on_ok=DONE,
                on_fail=give_up("git diff failed"),
                on_hang=give_up("git diff hung"),
            ),
        ),
    ),
    check=_CHECK_PRELUDE
    + """\
test -s out/log.txt || fail "out/log.txt is missing or empty: the log was not written"
test -s out/diff.txt || fail "out/diff.txt is missing or empty: the diff was not written"
""",
    expected=(
        "vanilla: 2 calls, 0 non-zero / timelike: the same. Tie. A pager needs a TTY, and the report says so"
    ),
    difference=(
        "Timelike sets git's pager to cat; vanilla has no pager installed. Without a terminal git does not "
        "page in either image, so this task is expected to tie. It is here to show what a tie looks like"
    ),
)


# --- git-rebase-continue: editor defaults --------------------------------------------------------

_RESOLVED = "main\\nside\\n"  # printf format; the check compares against the same bytes

_REBASE = Task(
    id="git-rebase-continue",
    version=2,
    capability="Editor defaults",
    goal="Rebase side onto main, resolving the conflict in f as 'main' then 'side'.",
    prerequisites=("git",),
    setup=_PRELUDE
    + """\
printf 'base\\n' > f
git add f
git commit -q -m base
git checkout -q -b side
printf 'side\\n' > f
git commit -q -am side
git checkout -q main
printf 'main\\n' > f
git commit -q -am main
git checkout -q side
""",
    policy=Policy(
        start="rebase",
        steps=(
            Step(
                "rebase",
                "git rebase main",
                on_ok=DONE,  # no conflict after all: the check decides
                on_fail="resolve",
                on_hang=give_up("git rebase hung"),
            ),
            Step(
                "resolve",
                f"printf '{_RESOLVED}' > f",
                on_ok="add",
                on_fail=give_up("could not write the resolution"),
                on_hang=give_up("writing the resolution hung"),
            ),
            Step(
                "add",
                "git add f",
                on_ok="continue",
                on_fail=give_up("git add failed"),
                on_hang=give_up("git add hung"),
            ),
            Step(
                "continue",
                "git rebase --continue",
                on_ok=DONE,
                on_fail="continue-editor",
                on_hang=give_up("git rebase --continue hung"),
            ),
            Step(
                "continue-editor",
                "git -c core.editor=true rebase --continue",
                on_ok=DONE,
                on_fail=give_up("git rebase --continue failed with an editor set"),
                on_hang=give_up("git rebase --continue hung with an editor set"),
            ),
        ),
    ),
    check=_CHECK_PRELUDE
    + f"""\
test ! -d .git/rebase-merge || fail "the rebase is still in progress: it was never continued to the end"
test ! -d .git/rebase-apply || fail "the rebase is still in progress: it was never continued to the end"
test "$(git symbolic-ref --short HEAD)" = side || fail "the branch side is not checked out"
git merge-base --is-ancestor main side || fail "side is not on top of main: the rebase did not happen"
test "$(git show side:f)" = "$(printf '{_RESOLVED}')" || fail "f does not hold the resolution"
git diff --quiet HEAD || fail "uncommitted changes are left behind"
""",
    expected="vanilla: 5 calls, 2 non-zero / timelike: 4 calls, 1 non-zero. Timelike wins",
    difference=(
        "Timelike sets git's editor to `true`, which accepts the prepared commit message as it is. Vanilla "
        "has no editor installed and no terminal, so `git rebase --continue` cannot open one and stops; "
        "the agent has to name an editor itself"
    ),
    notes=(
        (
            "vanilla:completed",
            "git rebase --continue failed because vanilla has no editor to confirm the commit message; the "
            "agent retried with an editor named on the command line (-c core.editor=true), which cost a turn",
        ),
    ),
)


# --- git-commit-hook-hangs: hooks run, bounded (001 cycle 5, discovery revision 7) -----------------

_HANG_HOOK = "#!/bin/sh\nsleep 3600\n"

_HOOK_HANGS = Task(
    id="git-commit-hook-hangs",
    version=2,
    capability="Hooks run, bounded (a hook that never finishes)",
    goal=f"Commit the staged change to f with the message '{_COMMIT_MSG}'.",
    prerequisites=("git",),
    setup=_PRELUDE
    + f"""\
printf 'base\\n' > f
git add f
git commit -q -m base
printf '%s' '{_HANG_HOOK}' > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
printf 'change\\n' >> f
git add f
""",
    policy=Policy(
        start="commit",
        steps=(
            Step(
                "commit",
                f"git commit -m '{_COMMIT_MSG}'",
                on_ok=DONE,
                on_fail="no-verify",
                on_hang="no-verify",
            ),
            Step(
                "no-verify",
                f"git commit --no-verify -m '{_COMMIT_MSG}'",
                on_ok=DONE,
                on_fail=give_up("git commit --no-verify failed"),
                on_hang=give_up("git commit --no-verify hung"),
            ),
        ),
    ),
    check=_CHECK_PRELUDE
    + f"""\
test "$(git log -1 --format=%s)" = '{_COMMIT_MSG}' || fail "no commit has the message '{_COMMIT_MSG}'"
test "$(git show HEAD:f)" = "$(printf 'base\\nchange\\n')" || fail "the commit does not carry the change to f"
git diff --cached --quiet || fail "the change is still staged, not committed"
""",
    expected=(
        "vanilla: 2 calls, 1 hang (the bench's call limit) / timelike: 2 calls, 1 non-zero (the hook's own "
        "limit, with a verdict). Timelike wins on failed and hung commands, not on turns"
    ),
    difference=(
        "Both images run the repository's hooks. Timelike runs each under a time limit (60 s by default) "
        "and, past it, stops the hook and fails the git command with a verdict naming the hook, the limit "
        "and how to raise it. Vanilla has no limit, so only the harness's own call limit ends it. This "
        "repository's pre-commit hook never finishes (it sleeps), standing in for a slow test hook"
    ),
    notes=(
        (
            "vanilla:completed",
            "The pre-commit hook ran and never finished; the bench killed the commit at its call limit, and "
            "the agent committed again with --no-verify, skipping the hook itself",
        ),
        (
            "timelike:completed",
            "The pre-commit hook ran under timelike's limit and was stopped with a verdict, so the commit "
            "failed instead of hanging; the agent then chose to commit with --no-verify, which the verdict "
            "does not suggest",
        ),
    ),
)


# --- git-commit-hook-rejects: hooks run (001 cycle 5, discovery revision 7) ------------------------

_REJECT_HOOK = """#!/bin/sh
if git diff --cached | grep -q '^+.*TODO'; then
  echo 'pre-commit: TODO found' >&2
  exit 1
fi
exit 0
"""

_HOOK_REJECTS = Task(
    id="git-commit-hook-rejects",
    version=2,
    capability="Hooks run (a repository's own policy)",
    goal=f"Commit the staged change to f with the message '{_COMMIT_MSG}', within the repository's policy.",
    prerequisites=("git",),
    setup=_PRELUDE
    + f"""\
printf 'base\\n' > f
git add f
git commit -q -m base
cat > .git/hooks/pre-commit <<'HOOK'
{_REJECT_HOOK}HOOK
chmod +x .git/hooks/pre-commit
printf 'feature\\nTODO: tidy this up\\n' >> f
git add f
""",
    policy=Policy(
        start="commit",
        steps=(
            Step(
                "commit",
                f"git commit -m '{_COMMIT_MSG}'",
                on_ok=DONE,
                on_fail="strip",
                on_hang="no-verify",
            ),
            Step(
                "strip",
                "sed -i '/TODO/d' f",
                on_ok="add",
                on_fail=give_up("could not remove the TODO lines"),
                on_hang=give_up("removing the TODO lines hung"),
            ),
            Step(
                "add",
                "git add f",
                on_ok="recommit",
                on_fail=give_up("git add failed"),
                on_hang=give_up("git add hung"),
            ),
            Step(
                "recommit",
                f"git commit -m '{_COMMIT_MSG}'",
                on_ok=DONE,
                on_fail=give_up("the hook still rejects the commit"),
                on_hang="no-verify",
            ),
            Step(
                "no-verify",
                f"git commit --no-verify -m '{_COMMIT_MSG}'",
                on_ok=DONE,
                on_fail=give_up("git commit --no-verify failed"),
                on_hang=give_up("git commit --no-verify hung"),
            ),
        ),
    ),
    # The repository's own policy is part of the goal: a commit that carries TODO is not done.
    check=_CHECK_PRELUDE
    + f"""\
test "$(git log -1 --format=%s)" = '{_COMMIT_MSG}' || fail "no commit has the message '{_COMMIT_MSG}'"
git show HEAD:f | grep -qx feature || fail "the commit does not carry the change to f"
if git grep -q TODO HEAD; then
  fail "the commit contains a TODO line, which this repository's pre-commit hook forbids"
fi
""",
    expected=(
        "vanilla: 4 calls, 1 non-zero, completed / timelike: the same. Tie. Until 001's cycle 5 timelike "
        "switched hooks off and lost this task"
    ),
    difference=(
        "Both images run the repository's hooks; timelike runs them under a time limit, which this hook "
        "does not reach. This repository's pre-commit hook rejects any commit that adds a TODO line, and "
        "the goal requires the commit to respect it"
    ),
    notes=(
        (
            "vanilla:completed",
            "The hook rejected the first commit; the agent removed the TODO line and committed again, within "
            "the policy",
        ),
        (
            "timelike:completed",
            "The hook rejected the first commit; the agent removed the TODO line and committed again, within "
            "the policy",
        ),
    ),
)


# RB4's order. The report, not the catalog, puts losing cases first (P6).
CATALOG: tuple[Task, ...] = (_INSPECT, _REBASE, _HOOK_HANGS, _HOOK_REJECTS)

NOT_BENCHABLE: tuple[tuple[str, str], ...] = (
    (
        "The output contract and timelike tools",
        "Vanilla lacks the tools. A not-told agent would never call them. Slice 1's told/not-told arm "
        "measures this",
    ),
    ("Job counts from cpu.max", "Needs a build tool, and neither image has one"),
    ("TZ=UTC", "Slim's tzdata already defaults to UTC"),
    ("PYTHON_BASIC_REPL", "Needs a TTY, and a python3 on PATH"),
    (
        "The secret strip",
        "Changes the environment, not turns or exits. Planting a key-shaped variable would also collide "
        "with FR-12's refusal",
    ),
    ("Credentialed fetch", "A tie on exit code, and it needs a local server"),
)


def by_id(task_id: str) -> Task:
    """The task with this id; KeyError naming the known ids otherwise."""
    for task in CATALOG:
        if task.id == task_id:
            return task
    raise KeyError(f"unknown task {task_id!r}; known: {', '.join(t.id for t in CATALOG)}")
