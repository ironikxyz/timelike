---
parent_branch: master
feature_number: "002"
status: In Progress
created_at: 2026-09-29T00:10:25+00:00
source_prompt: plan/.discover/prompts/02-speedup-bench.md
source_send: bridge/sends/02-rev1-20260929-000641.md
prompt_revision: 1
discovery_revision: 6
audited_against: [1]
slice: 0
---

# Feature: Speedup bench (slice 0)

## Overview

This is a bench that runs the same scripted task in a **vanilla** container and in the **timelike**
container, under a pinned harness and model. For each run it writes a trace, and from those traces a
report: completions, turns, tool calls, failed commands, hangs and wall-clock time. Tokens are never
the headline.

The bench is how timelike's value claims get made (P6: claims are measured). Without it, "fewer turns
for the same work" is an assertion. The bench grows with the project:
- slice 1 adds told and not-told arms, a second harness, and failure categories
- slice 2 adds repetitions and spread, losing-cases-first publishing, and incident replays

**This spec covers slice 0 (skeletal) only**, built from `bridge/sends/02-rev1-20260929-000641.md`.
Slice 0 is the thinnest path from end to end: one command, one task per capability timelike has today,
a deterministic fake agent, and a trace and report a person can read. The trace format and the task
catalog are designed so that slices 1 and 2 **add** to them without rewriting them (FR-14).

**The central risk (lore cross-stack P005).** A fake agent written alongside the bench can prove that
the bench runs, traces and reports. It cannot prove that timelike helps, because the fake agent's
behaviour was chosen by the same people who built timelike. Every report from a fake-agent run says so
on its first line (FR-9). A value claim needs a live run under a real harness and model. That is
operator-run, needs an API key, and is not a slice-0 criterion.

**Principles served:** P6 (claims are measured). P1's test ("every task ends completed or in a named
escalation") and P3's test (the told/not-told arm) are written against this feature's catalog. Slice 0
builds neither test, but it records how each run ended, which keeps P1's test answerable.

## User Scenarios

### Actors

- **Adopting developer** (decision-maker). Reads a bench report and reproduces it.
- **Operator** (administrative). Runs the bench, and decides what to build next from where timelike
  loses. Runs anything that needs Docker or an API key.
- **Harness** (autonomous intermediary). Drives an agent through a task by running tool calls in the
  environment under test. In slice 0 the only harness is the deterministic fake agent.
- **CI** (automated). The project's automated Docker lane. It runs the bench with the fake agent and no
  API key.

### Scenario 1: One command, two environments (SC-1)

1. The operator runs one bench command and names a task (or the whole catalog).
2. The bench builds or refreshes both images, checks that each is the revision it claims to be, and
   runs the task once in the vanilla image and once in the timelike image, under the same harness.
3. For each run it writes one trace, recording every tool call and the run's totals. It also writes a
   report comparing the two runs.

### Scenario 2: CI without a key (SC-2)

1. The automated lane runs the bench against the fake agent.
2. No API key is present anywhere in the run, and the run fails if one is found.
3. The lane passes only if both traces and the report were written and are well-formed. A success
   message is not enough; the artifacts are checked (H3, cross-stack P004).

### Scenario 3: Reading a report (DEMO → D2, SC-3)

1. The adopting developer opens a bench report for one task.
2. The first line says what produced the report. A fake-agent run says it is a demo run of the bench
   pipeline, not a test of timelike (FR-9, as amended).
3. The report compares vanilla with timelike on that task, in completion, turns and failed commands,
   with hangs, tool calls and wall-clock time beside them, and explains in words what the task tests,
   what happened in each image, and why the verdict is what it is (FR-9a). It names the revisions, harness and model
   it ran under, says the project's own maintainer measured it, and gives the command that reproduces
   it.

### Edge cases

- **A tool call hangs** (for example, a repository hook that never returns). The bench
  kills it at the per-call time limit, records a hang for that call, and returns to the harness a
  result that names the timeout. The run continues. A hang is a result, not a crash of the bench.
- **A run exceeds its overall time limit.** It ends as `hung`, and the trace is still written.
- **The timelike image is stale** (its revision label doesn't match the checkout being benched). The
  bench refuses to run and names both revisions (lore docker-compose Q004, cross-stack P003).
- **An identity stamp is empty or missing:** the timelike revision, the vanilla digest, the harness
  name and version, or the model id. The run fails with an error naming the missing stamp. An empty
  stamp is never written into a trace.
- **A command fails in one image and not the other.** That is the data the bench exists to collect. It
  is recorded, and it does not make the bench exit non-zero.
- **The trace directory is resolved by two processes.** The driver and the containers resolve paths on
  different filesystems (cross-stack P002). Traces are written by the driver only, never from inside a
  container under test.
- **An API key variable is present in the environment of a fake-agent run.** The run refuses to start.

## Functional Requirements

### Running

- **FR-1** A single bench command MUST run a named task, or the whole catalog, once in the vanilla
  image and once in the timelike image, under the same harness, model and task definition.
- **FR-2** Before running, the bench MUST make sure the timelike image is built from the current
  checkout, and MUST check the image's revision label against the checkout. On a mismatch it MUST
  refuse and name both revisions.
- **FR-3** The harness MUST reach both environments by the same invocation path a real harness uses:
  each tool call is a non-interactive `bash -c` (or `bash -lc`) with no terminal, started from outside
  the container. No harness, fake or real, may take a shortcut that the other harnesses cannot
  (cross-stack P005).
- **FR-4** Every tool call MUST have a time limit. A call that reaches it is killed and recorded as a
  hang, and the harness gets back a result that says so. Every run MUST also have an overall time
  limit.
- **FR-5** The bench driver MUST run in a container, not on the host (hard constraint: timelike ships
  as containers only). Neither image under test may hold the Docker socket (constitution H1, lore
  docker-compose P001).

### What is recorded (the trace)

- **FR-6** Each run MUST write exactly one trace. It records:
  - **Identity:**
    - the trace schema version
    - the task id and the task definition's version
    - the environment (vanilla or timelike)
    - the timelike image's git revision, or the vanilla image's digest
    - the harness name and version
    - the model id (the fake agent records its own identity here, never an empty value)
    - the bench's own revision
    - the command that reproduces the run
  - **Per tool call, in order:**
    - the command
    - exit code
    - duration
    - whether it hung
    - bytes emitted (stdout and stderr)
    - whether the harness cut the output it passed on, and how many bytes it passed
  - **Totals:**
    - turns
    - tool calls
    - non-zero exits
    - hangs
    - wall-clock time
  - **The ending:** exactly one of `completed`, `escalated`, `failed` or `hung`, with a one-line reason
- **FR-7** Token counts MAY be recorded. When the harness doesn't report them, the trace records their
  absence explicitly and never writes zero in their place.
- **FR-8** An empty or missing identity stamp MUST fail the run and MUST NOT be written (cross-stack
  P003, constitution H8).

### Reporting

- **FR-9** The bench MUST produce a report comparing the vanilla and timelike runs of each task:
  - The **first line** names what produced it. A report built from any fake-agent run MUST open with
    the operator's text, verbatim: `FAKE-AGENT BENCH PIPELINE DEMO RUN -- This is not a test of
    timelike, rather a test of the bench test itself (its presentation and usefulness to the human
    user). The agent's policy was written by timelike's own builders.` *(Amended by modify, send
    `…-080659`: the earlier line cautioned about what the run proves, and at D2 the caveat did not land.
    This one states what the run is.)*
  - The report states that it was measured by the project's own maintainer, and gives the command that
    reproduces it.
  - Headline figures per task, per environment:
    - completion (the ending)
    - turns
    - failed commands (non-zero exits)
    - hangs
    - tool calls
    - wall-clock time
  - Tokens appear only under an appendix heading, if at all.
  - Tasks where timelike did worse than vanilla are listed before tasks where it did better (P6
    constraint; slice 2 adds medians and spread).
- **FR-9a** *(Added by modify, send `…-080659`, from the D2 reading.)* Every task section MUST explain
  its outcome in plain words, so that a reader with only the report can say why each verdict is what it
  is. At minimum:
  - the capability the task tests, and what differs between the two images for it
  - the verdict in words, naming what decided it
  - for each arm, what happened call by call, and why any ending other than a clean completion ended
    that way (a failing check states its reason)
  - for a loss, why it is a loss

  An interpretation written with a task is printed only when the run ended the way it describes.
- **FR-10** The report MUST be built from the traces alone, so that any trace set can be re-reported
  without re-running it.

### Fake agent and CI

- **FR-11** A deterministic fake agent MUST drive every catalog task. Given the same outputs from the
  environment, it takes the same next step, with no randomness and no network. Its policy is written
  per task, it reacts only to what it observes (exit codes, output, hangs), and it is versioned. Its
  version is stamped in every trace.
- **FR-12** The bench MUST run end to end in the automated lane against the fake agent with no API key.
  A fake-agent run MUST refuse to start if an API-key-shaped variable is present in its environment.
- **FR-13** The automated check MUST verify the artifacts, not the exit message: two well-formed
  traces per task, with non-empty stamps, and a report whose first line carries the fake-agent
  statement.

### Extensibility (slice 0 builds none of this)

- **FR-14** The trace schema and task catalog MUST let slice 1 add the following without changing any
  existing field's meaning:
  - an arm label (told or not-told), and counts of timelike tool invocations
  - a second harness
  - a failure category per failed command

  Traces are versioned. Harness identity is a field, never an assumption. Every failed call keeps its
  command, exit code and stderr head, so that it can be categorised later.

### Contract and supply chain

- **FR-15** The bench's command-line tools MUST follow the output contract from feature 001, and MUST
  pass `timelike-conform`.
- **FR-16** Every image the bench adds (the vanilla image and the driver) MUST pass the supply-chain
  gate (`make scan`, constitution H9) under the revision-5 baseline rule.

## Success Criteria

Criteria for slice 0, cited by distinguishing text as the send gives them. The slice-1 and slice-2
criteria in the send are **not** in this spec: a spec built from a slice-0 send isn't incomplete
against slices it was never sent.

### Automated

- **SC-1** One command runs a task in both a vanilla image and the timelike image, and writes a per-run
  trace with turns, tool calls, non-zero exits, hangs and wall-clock time. *(P6, slice 0)*
- **SC-2** The bench runs end to end in CI against a deterministic fake agent, without any API key.
  *(P6, slice 0)*

### Manual

- **SC-3 (DEMO → D2)** The adopting developer reads a bench report comparing a vanilla container with
  timelike on one task, in turns and failed commands. *(D2, slice 0)* It stays unconfirmed until a
  person has looked. The cycle report says whether a fake-agent or a live report was shown.

### Measurable outcomes

- One command produces two traces per task and one report, with no manual step in between.
- 100% of traces carry non-empty identity stamps, and a run with a blanked stamp fails. This shows the
  check can fail.
- 0 API-key variables present in a CI run, and a run with one planted refuses to start.
- A task containing a deliberately hanging call ends within its time limit, with the hang recorded.

## Key Entities

- **Task.** One scripted piece of work, with an id, a version, a goal, a setup, and a check that
  decides completion. It is the same in both environments.
- **Task catalog.** The set of tasks. In slice 0, one task per capability timelike ships today.
- **Environment.** Either vanilla or timelike. Each is identified by digest or revision.
- **Harness.** What drives the agent through a task. It has a name and version, and a model id.
- **Fake agent.** A deterministic harness with a scripted policy per task. It proves the pipeline only.
- **Run.** One task, in one environment, under one harness. It produces one trace.
- **Trace.** A versioned record of a run: its identity, the tool calls, the totals, and the ending.
- **Tool call.** One command the harness ran. It carries the exit code, duration, hang, and bytes
  emitted and passed.
- **Report.** A comparison built from traces: headline figures, losing tasks first, and tokens in an
  appendix.

## Out of Scope

- **All slice-1 and slice-2 criteria:**
  - told and not-told arms
  - a second harness
  - failure categories
  - five or more repetitions, with medians and spread
  - incident replays
  - publishing from the README
- **A live harness run as a criterion.** The trace has room for a real harness and model (FR-6), and
  the operator may do a live run. It needs an API key. **No key goes into either image under test, into
  CI, or into this repository** (P4; Adele, feature 12, doesn't exist yet). If a live harness adapter is
  built at all in this slice, the key reaches the harness process only, which runs outside the
  environment under test.
- **Value claims.** No report from this slice may be read as evidence that timelike helps.
- **Revising the output contract.** Two contract questions are flagged by plan at discovery revision 6:
  - a mandatory closing line
  - a byte cap on output

  Both are bench-gated and out of scope. The trace records bytes emitted per call, and whether the
  harness cut them (FR-6), so that both become answerable later.

## Assumptions

1. **"Vanilla image"** means the same base, the same unprivileged agent user, and the same task
   prerequisites as the timelike image, **without** anything timelike adds:
   - the same base is Debian trixie-slim, by the digest 001 pins
   - the task prerequisites are OS packages a task declares it needs, such as git
   - what timelike adds, and vanilla lacks: its layers, tools, environment defaults (`/etc/gitconfig`,
     the shell-env hook, the static ENV) and announcements

   This is the reading closest to P6's "against a vanilla environment". The report header names the
   vanilla digest and this definition, because the comparison means only what its baseline is.
2. **"CI"** means the project's automated Docker lane. No hosted CI exists and no remote is configured.
   The bench's CI check is a step the lane runs from outside the containers, with the fake agent. It is
   run by the operator on the host (research R10 of feature 001), and it is written to run unchanged
   under any CI that has Docker.
3. **Harness location:** the harness runs **outside** the environment under test. It runs each tool
   call as a non-interactive shell exec into the task container. This is 001's Assumption 1 invocation
   path (`bash -c` / `bash -lc`, no TTY), and it is the same path for both environments, so neither
   gets a shortcut. A real harness that installs inside the container (an npm CLI, for example) is a
   slice-1 question. It would have to be installed identically into both images, and it would go
   through the supply-chain gate.
4. **Harness and model pin.** Each trace records the harness name and version and the model id. For
   the fake agent these are its own name, its version and the model id `none (deterministic fake
   agent)`. The pin is recorded, never inferred, and an unpinned run is refused (FR-8).
5. **The slice-0 catalog:** one task per capability timelike ships today. Feature 001 ships
   non-interactive git defaults, the output contract, and container-derived defaults. The planning step
   chooses the tasks. Each is written so that a vanilla failure mode shows up in the trace as a hang or
   a failed command, rather than being hidden by the task's own setup. *(Corrected at plan, research
   RB3. This assumption first gave "git opening an editor with no terminal" as a vanilla hang. On this
   invocation path, with no terminal and no `TERM`, vanilla git's editor and pager traps **fail fast**,
   or make no difference at all. The only guaranteed vanilla hang is a repository hook that doesn't
   return. A capability that makes no observable difference on this path is recorded as such in the
   catalog, not dressed up as a task.)*
6. **The fake agent's policy is the same in both environments.** It is written as "do X; if that fails
   or hangs, do Y". It never branches on which environment it's in. Any difference in turns comes from
   the environment's responses, not from the script. This is necessary but not sufficient (P005), which
   is why the first-line statement exists.
7. **Time limits** per tool call and per run are documented constants, overridable per run. The
   planning step sets their values. The per-call limit is well above 001's 20-second git bound, so
   that a slow but concluding call is not recorded as a hang.
8. **The D2 demo** is shown with a fake-agent report unless the operator chooses a live run. The cycle
   report says which one was shown.
9. **The driver's interpreter** is CPython 3.14.7, managed by uv, as in the agent image, running in
   the bench driver's own container. The planning step records the exact arrangement.
