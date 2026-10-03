# Research — 003 Concluding run (slice 0)

Each entry gives the decision, the reasoning, and the alternatives considered. Experiments that fork or
hang were run under `setsid --wait timeout -k 5 N … </dev/null` (cycle 5 process failure 3). None of
them matched a command line to find a process (process failure 2).

## R1 · Exit codes: pass-through (ruled, discovery revision 9)

- **Decision:** `run` exits with the command's own code, including 126, 127 and 128+n. It exits 124
  only when its own limit fired, 2 on a usage error before anything runs, and 1 on its own failure.
  `cause` and `command_exit` tell the two apart.
- **Rule relied on:** discovery Soft Constraints, Agent output contract, *(Clarified, revision 9)*.
  The ruling: `../bridge/feedback/03-20260930-235857-exit-pass-through.md` § Resolution.
- **Consequences for 001's contract** (spec FR-20 to FR-24):
  - `output-contract.md` (lines 36 and 83)
  - `agent-info.schema.json` (`passes_exit`)
  - `event.schema.json`: its `exit` enum would reject a passed-through 42 under C7. Plan's list did not
    name it; it is found here
  - `agentio`
  - conformance C6
- **Mapping from what the process reports to the code:**
  - `Popen.returncode = -n` → 128+n
  - `FileNotFoundError` at exec → 127
  - `PermissionError`, `IsADirectoryError` or ENOEXEC at exec → 126

  This is bash's own mapping, so `$?` is what the shell would have shown.

## R2 · Not blocking on a held output: output goes to a file, never a pipe

- **Decision:** the command's stdout and stderr are the **same file descriptor**, opened `O_APPEND` on
  the log. `run` waits on the **process**, not on end-of-file.
- **Why:** a pipe stays open while any holder lives. That is the G3 hang (`npm run dev &`), which is
  exactly what wrappers that read the command's output through a pipe get wrong. A file has no reader
  that can block.
- **Experiment (host, Python 3.12):** `bash -c "… & sleep 30 & echo started; exit 3"`, with output to
  a file. `wait()` returned rc 3 after **0.0 s**, while three descendants still held the file open.
- **Cost:** the agent sees nothing until the command ends. That is acceptable: it reads the verdict,
  not a stream, and `--verbose` adds nothing here. Ordering between stdout and stderr is the kernel's
  write order on one descriptor. That is the order a terminal would show.
- **Alternatives:**
  - A pipe, a reader thread, and a cut-off at the command's exit. It is more code, and it is what
    hangs elsewhere
  - A pty: rule 4 forbids it, and a pty brings in ANSI output

## R3 · Finding the whole tree: become a child subreaper, then walk `/proc` by parent

- **Decision:** at start, `run` calls `prctl(PR_SET_CHILD_SUBREAPER, 1)` through `ctypes` (stdlib,
  H5). Every orphan from the command's tree is then re-parented to `run` instead of to PID 1. The tree
  is then the transitive closure of "parent is `run`", read from `/proc/<pid>/stat` field 4. Zombies
  (state `Z`) are skipped.
- **Why:** a process group or session does not hold the tree:
  - A nested `timeout` leads its own **process group**. That is cycle 5 process failure 1, where
    about 1,000 processes escaped every outer limit.
  - `setsid` starts a new **session**.

  The parent link survives both, and the subreaper keeps it for orphans.
- **Experiment (host):** the command was `timeout 50 bash -c 'setsid sleep 40 & sleep 40' & sleep 30
  & …; exit 3`. After it exited, the parent walk from `run` found 5 descendants:
  - `timeout`, in its own pgrp
  - a `sleep` in a **new session** (`setsid`)
  - the inner `bash` and two `sleep`s

  All had been re-parented to `run`. SIGKILL to each, then reaping, left 0.
- **Start-up cost:** `import ctypes` adds about 3.2 ms (`-X importtime`, host). The tool budget is <
  100 ms p95, and the measured base is about 40 ms.
- **What it cannot reach:** a descendant re-parented to a **nested** subreaper inside the tree is
  reached through that subreaper, which is itself in the tree. A process that changes its parent by
  some other means does not exist on Linux. A process that daemonizes through a helper *outside* the
  tree (for example `systemd-run`, or a request to a server) is not a descendant, and is not claimed.
  The spec's Assumptions say so.
- **Alternatives:**
  - `killpg` alone: misses nested groups, as in process failure 1
  - matching by session id: misses `setsid`
  - a cgroup per call: needs privilege the agent does not have (P4), and a delegated cgroup is not
    on this stack
  - `pgrep -f`: rejected, process failure 2

## R4 · Stopping the tree on timeout, without a fork race

- **Decision:**
  1. Send SIGTERM to every process in the tree.
  2. Wait up to **2 s** for the tree to empty, reaping as it goes.
  3. Then **freeze and kill**: SIGSTOP everything in the tree, re-scan, SIGSTOP any newcomers, and
     repeat until a scan finds no new process (at most 50 rounds).
  4. SIGKILL everything, then SIGCONT, so a stopped process can take the kill.
  5. Reap, and re-scan until the tree is empty or 3 s have passed.
- **Why:** a forking process can outrun a single kill sweep. Stopping first makes the set stable.
- **If anything survives the last scan:** the verdict names it (pid and name) as **not stopped**. It
  never claims a clean stop it did not observe (H3, cross-stack P004).
- **Grace period:** 2 s for SIGTERM, plus at most 3 s of kill and re-scan, so a hang ends by limit +
  5 s at worst (spec, Measurable outcomes).

## R5 · Detached children on a normal exit

- **Decision:** when the command's own process has exited, `run` reaps it, waits **100 ms** for
  backgrounded processes to settle, and lists:
  - the tree, as in R3, minus zombies
  - and processes of the same uid holding the log open for **writing**, read from `/proc/<pid>/fd`
    links plus the `flags` in `/proc/<pid>/fdinfo/<fd>`

  Each is named as a detached child with its pid and `comm`. None is stopped.
- **Why write-only:** an agent may `tail -f` an older log in parallel, and that reader is not ours.
- **Bound:** the scan reads `/proc` once, in milliseconds in a container. The 2-second criterion is
  dominated by the 100 ms settle.
- **Amended at T016: the settle is paid only when something is left running.** A child the command
  forked exists before the command exits, so a first scan decides whether there is anything to name.
  The usual call pays nothing: `run --json true` went from 176 ms to 75 ms (p95 78 ms, host).
- **Process-safety in tests:** the child writes its own pid to a marker file. The test compares the
  verdict with that file and then kills that pid. It never matches command lines (process failure 2).

## R6 · Argument parsing: split at the command, then parse `run`'s own prefix

- **Decision:** `agentio` gains a pass-through mode (the tool declares `passes_exit=True` and a
  `command` positional). It splits `argv` at the first word that is not one of the tool's options,
  using the parser's own option table to know which options take a value, or at `--`. Only the prefix
  goes to `argparse`, and the rest becomes `args.command`.
  - `--json` and `--verbose` are detected in the **prefix only**, so `run grep --json x` keeps rule
    14's error mode and the verbosity of `run`'s own call.
- **Why not `argparse.REMAINDER`:** its handling of `--` and of options after the first positional
  changed between 3.12 (host) and 3.13+ (the image runs 3.14). A split that `agentio` owns behaves the
  same on both, and conformance C5 (an unknown flag exits 2) still holds, because an unknown option
  in the prefix reaches `argparse`.

## R7 · Name: `run`

- **Decision:** `/opt/timelike/bin/run`.
- **Why:** it is the research bundle's name, and discovery revision 6's. It is also the verb agents
  already use, as in `npm run` and `cargo run` (P3).
- **Shadowing:** Debian trixie-slim ships `run-parts`, not `run`. An e2e test asserts that `type -a run`
  resolves to exactly one file, `/opt/timelike/bin/run`, under `bash -c` and `bash -lc`. The test
  checks it rather than assuming it.

## R8 · Sections within the cap

- **Decision:** for a cap L (default 200), the sections are:
  - **head:** ⌊L/4⌋ lines (50)
  - **errors:** up to ⌊L/10⌋ lines (20), only from beyond the head and before the tail, so no line
    is shown twice
  - **tail:** ⌊L/2⌋ lines (100)

  For L < 8, the head and tail are at least 1 each, and the errors may be 0. Output is cut only when
  its line count is greater than L.
- **Why weighted to the tail:** a build or test run reports its summary and its last failure at the
  end. The head shows what started and how.
- **The more command:** `sed -n A,Bp <log>`, **one range over the whole gap** (amended at T011).
  Agents were trained on `sed -n`, which reads the log and never runs the command again.
  - One range per gap between error lines could reach 21 ranges and run past the `COLUMNS` cut,
    which would break the command. So the single range also re-prints the few error lines already
    shown. The omission count stays exact: it counts only lines that were not printed.
  - A cap below head + tail (`--limit 1`) shortens the tail, so the gap is never empty. `run` always
    cuts its own output when it exceeds the cap, so `agentio`'s generic cut (and its re-run) never
    applies.
  - `agentio`'s generic "more" (re-run the tool with `--limit 0`) would **run the command a second
    time**, which is wrong for any command with effects. So `run` supplies its own more command to
    `agentio`.
- **Streaming:** the log is read once, line by line. That gives the count, the head, a bounded
  `deque` for the tail, and the first error matches. Memory is bounded by the cap, not by the log
  (a 5 GB log is fine).

## R9 · Error patterns

- **Decision:** a fixed, case-sensitive set of whole-word or prefix matches:
  - `error`, `Error`, `ERROR`
  - `FAIL`, `FAILED`, `Failed`, `failed`
  - `fatal`, `Fatal`, `FATAL`
  - `Traceback`, `panic:`, `Exception`
  - `not found`, `No such file`, `Permission denied`, `denied`
  - `undefined reference`, `cannot`
  - `Segmentation fault`, `Killed`, `Aborted`

  The list is printed in the manifest (`error_patterns`) and summarized in `--help`.
- **Why fixed:** rule 11 (deterministic). An agent can predict what will be flagged.
- **Known misses and false hits:** both are accepted for slice 0. A line saying "0 errors" is flagged;
  that costs one line of 20. Slice 1 may tune the set from bench traces (P6).

## R10 · Default limit: 100 s, `TIMELIKE_RUN_TIMEOUT`, `--timeout`

- **Decision:** 100 s.
- **Why 100:** below Claude Code's 120 s call limit (the figure 001's 60 s hook limit was sized
  against), with 5 s for the stop sequence and 15 s of margin for the harness's own overhead. At 110,
  a slow stop or a busy host could let the harness kill the call first, and then the call ends with
  no verdict, which is what P2 forbids.
- **Precedence:** `--timeout` beats `TIMELIKE_RUN_TIMEOUT`, which beats the default. Both accept
  seconds as a positive decimal. An invalid environment value is a usage error naming the variable,
  never silently replaced. The verdict says which source set the limit.

## R11 · Rule 11 and the duration (reading raised as FOR-MENTOR Item 10)

- **Decision:** the verdict always shows the duration, to 0.1 s.
- **Rule relied on:** prompt 01's rule 11, *"no **timestamps** except behind `--verbose`"*. A duration
  is the measured result `run` reports, like `time(1)`'s. It is not a timestamp.
  - `output-contract.md` line 18 says "timestamps **and timing**". That is code/'s wording, and wider
    than the rule (the same pattern as line 83). It is **not** reworded here: Item 10 asks plan to
    confirm.
- **If plan rules otherwise:** the duration moves behind `--verbose`, a one-line change in `run`.

## R12 · Log location and naming

- **Decision:** `<scratch>/<session>/run/<UTC yyyymmddThhmmssZ>-<pid>.log`, created `O_EXCL`, mode
  0600, in a 0700 directory made through `agentio`'s `_session_dir`. The verdict prints the absolute
  path.
  - P002: the agent's next command runs in the same container, as the same user, so the path resolves
    to the same file.
- **If the log cannot be created,** the command does not run: exit 1, with a structured error naming
  the path. Running a command whose output cannot be kept would break the verdict's promise.

## R13 · Stdin

- **Decision:** the command's stdin is `/dev/null`.
- **Why:** under a harness, stdin may be a pipe that never closes, or nothing. A command that prompts
  then waits forever. End-of-file makes it fail fast and say so (P2, rule 4).
- **What this costs:** `cat x | run grep y` does not pass `x` to `grep`. The help says to write it
  as `run sh -c 'cat x | grep y'`.

## R14 · Line endings and very long lines

- **Decision:** the log is byte-exact. For display, lines are split on `\n`, decoded as UTF-8 with
  `errors="replace"`, and `\r` is stripped (`agentio`'s `_clean`). Each line is then cut at `COLUMNS`
  with the contract's marker.
- **A final line with no newline counts as a line.** An empty output is 0 lines.
