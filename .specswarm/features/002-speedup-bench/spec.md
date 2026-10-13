---
parent_branch: master
feature_number: "002"
status: In Progress
created_at: 2026-09-29T00:10:25+00:00
source_prompt: plan/.discover/prompts/02-speedup-bench.md
source_send: bridge/sends/02-rev1-20260929-000641.md
prompt_revision: 1
discovery_revision: 6
audited_against: [1, 8]
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
*(Amended in Cycle 4, declared: slice 1 is now specified as well, in § Slice 1 below, from send
`bridge/sends/02-rev8-20261013-064725.md`. The slice-0 text above and below stays as written, except where a note
says otherwise.)*

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
- **The verdict order** *(Added revision 8; copied from prompt 02's constraints by modify Cycle 2, send
  `…-095251`.)* "A task's verdict compares, in order: ending, turns, hangs, failed commands. Each call is
  counted once per row (a hung call is one failed command and one hang, and hangs are compared first).
  Wall-clock time and tool calls are reported and never decide. The verdict sentence quotes only counts that
  appear in the report's table (P6, P2)."
  - *(Amended in Cycle 4, declared: **met since Cycle 4** by FR-48. `report.py` compares ending, turns, hangs, then
    failed commands, and its sentence quotes only table counts; `data-model.md` step 3 and decisions T016 are
    corrected or annotated. The note below records slice 0 as it was.)*
  - **Slice 0 does not meet it, and is not changed for it.** Its verdict compares `nonzero_exits + hangs`
    as one tiebreak after turns (`bench/benchlib/report.py:119`; `data-model.md` § Comparison and report,
    step 3), so a hung call counts twice and hangs are not compared first, and the verdict sentence quotes
    that sum (`report.py:227`). T016's assumption is where it came from. Plan's ruling (b) on
    `bridge/feedback/02-20260930-060406-hang-counted-twice.md` carries the change to 02 slice 1, because
    slice 0's reports are labelled fake-agent runs (FR-9).
  - The slice-1 criterion that revision 8 added with it (two arms ending the same way in the same turns are
    ranked by hangs, then failed commands) is not copied here: this spec carries no later-slice criteria
    (§ Success Criteria).
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
  gate (`make scan`, constitution H9) under the revision-5 baseline rule. *(Cycle 4 addendum, lane 02s1-a item 4: an
  SBOM that catalogues no packages fails the gate, naming the image, because every image the scan knows holds
  software; and the harness image's SBOM takes its two harnesses from their pins, `opencode-ai` and `@openai/codex`
  at `OPENCODE_VERSION` and `CODEX_VERSION`, because Syft catalogues nothing in a binary-only image.)*

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

- **All slice-1 and slice-2 criteria:** *(Amended in Cycle 4, declared: the three slice-1 items below are in scope
  since Cycle 4, § Slice 1; the slice-2 items stay out.)*
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
  environment under test. *(Slice 1, Cycle 4 addendum: superseded by FOR-MENTOR Item 25's ruling (b), `bridge/feedback/02-20261013-071257-item-25-the-relay-holds-the-key.md`
  — the relay in the bench driver holds the key, and no harness or agent command holds it; FR-26, FR-30.)*
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
   through the supply-chain gate. *(Amended in Cycle 4, declared: answered by FR-24. A live harness runs inside the
   task container, as the agent's tool calls must, but is installed into neither image: it is mounted read-only from
   a harness image that goes through the supply-chain gate. The fake agent still runs from outside, as here.)*
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

## Slice 1 (Cycle 4, send `bridge/sends/02-rev8-20261013-064725.md`; natural)

Added work on a body that stays true, recorded here, declared (`modify.md` § Cycle 4). Revision 8 is already in
`audited_against` (modify row 4); nothing is appended. Revision 8's constraint, copied into § Reporting in Cycle 2 and
not met by slice 0, **is met by this cycle** (FR-48); the note under § Reporting is amended to say so.

Slice 1's criteria, verbatim from the send:
- *"Each run is labelled told or not-told, and the report counts timelike tool invocations per arm"* _(P3, slice 1)_ —
  **SC-4**.
- *"The same task catalog runs under two harnesses and the report shows results per harness"* _(P7, slice 1)_ —
  **SC-5**.
- *"Two arms that end the same way in the same number of turns are ranked by hangs, then by failed commands, with each
  call counted once, and the verdict sentence states only counts that appear in the table"* _(P6, slice 1; revision 8)_
  — **SC-6**.
- *"Failed commands are grouped into categories including command not found, module not found, timeout, memory kill and
  network denial"* _(P2, slice 1)_ — **SC-7**.
- *DEMO: "the Adopting developer compares timelike tool adoption between a told arm and a not-told arm, under two
  harnesses"* (D11, Manual) _(slice 1)_ — **SC-8**. Unconfirmed until the mentor's live run and the operator's reading.

Slice 0's SC-1 and SC-2 stay in force and are re-established. Slice 2's criteria (repetitions and spread, tokens under
an appendix heading as a criterion, incident replays, publishing, D25) are not built and not cited.

### Actors (slice 1)

- **Live harness** (autonomous intermediary). OpenCode or Codex CLI, pinned, driving the pinned model through a task
  inside the task container. It runs its own shell; the bench does not run its tool calls.
- **Model provider** (external). OpenRouter, reached only by a live harness, only through the driver's relay, and only
  on the operator's key.
- **Model stand-in** (automated). timelike's own HTTP server speaking the provider's protocols with scripted tool calls,
  so the live path runs end to end in the lane with no key.

### Scenarios (slice 1)

**Scenario 4: three arms (SC-4).** For each task the bench runs the vanilla arm, the timelike **not-told** arm (the
timelike image, its tools on PATH, no announcement placed) and the timelike **told** arm (the same image, with the
announcement placed by `timelike announce --install` before the harness starts, as the agent image's entrypoint does).
The report counts, per harness and arm, the calls that ran a timelike tool by name, and separately the calls that went
through timelike's shims or guards.

**Scenario 5: two harnesses (SC-5).** The operator runs the catalog under OpenCode and Codex CLI with the same model.
The report has one section per harness. Within a harness the arms are compared; harnesses are never compared with
each other, because each counts turns from its own events.

**Scenario 6: a live run that cannot finish (natural).** OpenRouter answers 429, or the harness exits 1, or the run
reaches its turn cap. The run is recorded as a row ending `stopped`, with the cause named. It is listed under
"Not compared (infrastructure)" and never counted as a loss for either image.

**Scenario 7: the mentor's live run.** One command from `code/` on the host, with `BENCH_KEY_FILE` naming the key file,
prints its plan (cells, harnesses, model, caps and a spend estimate) before the first request, then runs. `--dry-run`
prints only the plan.

**Scenario 8: categories (SC-7).** Every failed call carries exactly one category. `timelike-bench categories --probe`
runs one real failing command per category in each image and prints how each was categorised.

### Functional requirements (slice 1)

**Arms (SC-4)**
- **FR-17** Every run carries an **arm**: `vanilla` (the vanilla image; neither told nor not-told), `not-told` (the
  timelike image, no announcement placed) or `told` (the timelike image, the announcement placed). The report labels
  them `vanilla`, `timelike, not told` and `timelike, told`. The vanilla arm has no placement because it has no
  timelike, so "told" does not apply to it.
- **FR-18** The told placement runs `/opt/timelike/bin/timelike announce --install` as `agent`, with `HOME=/home/agent`
  and `CODEX_HOME=/home/agent/.codex`, after the task's setup and before the harness starts, outside the counted run.
  Its result is recorded in the trace. A placement that does not report the harness's own file as `placed`, `replaced`
  or `current` ends the run `stopped` (cause `placement`). Nothing about 007's placement changes; the bench runs it
  because task containers start with `--entrypoint sleep`, which skips the entrypoint that runs it in the product.
  The fake agent cannot read a placement, so its told and not-told arms behave alike; the report says so.
- **FR-19** A call **invokes a timelike tool** when a command word in it (after splitting on `;`, `&&`, `||`, `|`, `&`
  and newlines, skipping leading `NAME=value` assignments and the wrappers `command`, `exec`, `env`, `nohup`, `time`
  and `timeout <n>`) has a base name in the run's **timelike tool list**. The list is read once per invocation from the
  timelike image (`timelike tools --json`, the entries of kind `timelike`) and recorded in every trace of that
  invocation, vanilla's included. A call that runs a shimmed installer (`pip`, `pip3`, `uv`, `npm`, `npx`, `pnpm`; 013)
  or a guarded command (`rm -r…`, `git reset --hard`, `git push --force` or `-f`, `git clean`; 005) by name is
  **through timelike**, counted separately and never as adoption: the agent did not choose a tool. In the vanilla arm
  neither count applies and the report shows `—`. Counts come from the trace's commands, never the model's words.
- **FR-20** Per harness, the report has an **adoption** table: for each arm, runs, tool calls, calls invoking a
  timelike tool, the tools invoked with their counts, and calls through timelike.

**Harnesses (SC-5)**
- **FR-21** Three harnesses: `fake` (slice 0's deterministic agent; the default, and CI's), `opencode` (OpenCode
  **1.19.0**) and `codex` (Codex CLI **0.162.1**). The second live harness is Codex CLI, chosen on evidence (research
  RB12): Claude Code is excluded because OpenRouter's own guide says it "is only guaranteed to work with the Anthropic
  first-party provider", and this model is not Anthropic's.
- **FR-22** The same catalog runs under every harness selected. The report has one section per harness, each with its
  own verdicts, adoption table and category table. Arms are compared within a harness, never across harnesses.
- **FR-23** Each live harness is pinned in `pins.env` by version and by the npm registry's `sha512` integrity of its
  linux-x64 package, and the harness image refuses a tarball that does not match. Each trace records the version the
  harness itself reports (`--version`, in the task container) beside the pin; a disagreement refuses the run
  (cross-stack P003).
- **FR-24** A live harness runs **inside the task container**, as `agent`, in the task directory, so its tool calls
  run there as the agent's would. It is mounted read-only at `/opt/bench-harness` from one harness container per
  invocation (`docker create` from `timelike-bench-harness:local`, then `--volumes-from <it>:ro` on every task
  container). Every arm gets the same mount. **Neither image under test gains anything.**
- **FR-25** **Network, live runs only.** The task containers of a live invocation join a per-invocation
  `--internal` Docker network whose only other member is the driver. A harness reaches the model only through the
  driver's relay (FR-26). The agent's commands have no other network, in every arm alike, which is what makes network
  denial producible live. Fake-agent runs keep `--network none`. *(Cycle 4 addendum, Item 25 (b), condition 5: an
  agent's command shares this network with the harness, so it can reach the relay too. That is use, not reading: the
  relay holds the key, and every request counts toward the caps whoever sent it.)*
- **FR-26** **The relay** (`benchlib/relay.py`) runs in the driver. It forwards requests to the upstream
  (`https://openrouter.ai`, or the stand-in), streams the response back, and reads from each response its status, its
  generation id, the model id that answered, and its usage (tokens, and cost when present). It never logs, stores or
  writes a request header. It enforces the turn cap and the spend cap by answering any further request with an error
  that names the cap. A **turn** at the relay is a request that offers tools (a harness's title or summary request
  offers none and is not a turn). *(Cycle 4 addendum: amended by FOR-MENTOR Item 25's ruling (b), `bridge/feedback/02-20261013-071257-item-25-the-relay-holds-the-key.md`.)*
  - **It holds the key** (condition 1). It drops the `Authorization` header a request arrives with, and every other
    credential-carrying header (`X-Api-Key`, `Api-Key`, `Cookie`), placeholder or not, and adds its own
    `Authorization: Bearer <key>`. Against the stand-in there is no key and it adds none.
  - **It forwards only what a harness needs** (condition 4): `POST /api/v1/chat/completions`, `POST /api/v1/responses`
    and `GET /api/v1/generation`, to its one upstream, and a model request only when its body names the pinned model.
    Anything else is answered 403 with a named verdict, recorded under the run's `refused` counts, and never forwarded:
    `route-not-allowed` (another method or path, or a target naming another host), `no-model`, or `other-model`. A
    request for another model ends the run `stopped`, cause `model-refused` (FR-36).
  - **Every request counts, whoever sent it** (condition 5): the same rules for turns and spend apply to any request
    that reaches it. The relay cannot tell a harness's request from an agent command's: both come from the same
    address, and anything the harness carries to identify itself the agent can read too. So nothing is attributed to
    a sender, and the run's relay summary says so (`senders`).
- **FR-27** The model is pinned to a dated id, `deepseek/deepseek-v4-pro-0813` (`BENCH_MODEL`). An id without a date
  suffix (four or eight digits after the last `-`), or one ending `-latest`, is refused before anything runs. Each
  trace records the pinned id and the ids OpenRouter answered with (P003); a different answer is recorded, not refused.
- **FR-28** Harness configuration is given at exec time, and no configuration file is written into the task directory:
  OpenCode through `OPENCODE_CONFIG_CONTENT` (provider `openrouter` with the relay's base URL and the key variable read
  from the environment, which holds the placeholder (FR-30), `model` and `small_model` both the pinned id, every permission allowed, sharing and autoupdate off),
  `--pure`, `--format json`, and `OPENCODE_DISABLE_MODELS_FETCH`, `_DEFAULT_PLUGINS`, `_LSP_DOWNLOAD`, `_CLAUDE_CODE`,
  `_SHARE` and `_AUTOUPDATE`; Codex through `-c` overrides (provider `openrouter`, the relay's base URL, `env_key`,
  `wire_api = "responses"`, `web_search = "disabled"`, analytics and the update check off), `--strict-config`,
  `--json`, `--skip-git-repo-check` and `--dangerously-bypass-approvals-and-sandbox` (the task container is the
  sandbox, which is the case the flag is for). The prompt is the task's goal and one line naming the directory.

**The key (P4)**
- **FR-29** A live run reads the key from the file `BENCH_KEY_FILE` names. `bench/run.sh` refuses it on the host unless
  it is a regular file outside the repository, mode `0600`, owned by the user running the bench; the driver checks
  the same again on the read-only mount (`/run/timelike-bench/key`). The key is never read from argv, a compose file,
  an image's `ENV`, a container's `Config.Env` or a file in `code/`. Every refusal names the path and the failing
  property, never the value (exit 4).
- **FR-30** ~~The key reaches the harness process only: `docker exec -e OPENROUTER_API_KEY` for the harness's exec, with
  the value in the docker CLI's own environment and only the name on argv. Setup, the placement, the check, the
  version probe and every other exec get no key. It goes when the task container is removed.~~ *(Cycle 4 addendum,
  superseded by FOR-MENTOR Item 25's ruling (b), `bridge/feedback/02-20261013-071257-item-25-the-relay-holds-the-key.md`, conditions 2 and 3:)* **No harness and no agent command
  holds the key.** Every harness's `OPENROUTER_API_KEY` holds one fixed, documented placeholder,
  `placeholder-the-bench-relay-adds-the-key`, the same for every harness and run; it is not shaped like a key (words,
  no provider prefix), and both harnesses refuse to start with the variable unset. The key lives in the driver's
  memory, read from `BENCH_KEY_FILE` at start (FR-29), and is used by the relay (FR-26) and by the driver's own
  generation-stats lookup (FR-35). It is **never** in the driver's environment, a `docker exec -e`, a container's
  `Config.Env`, a command line, a mount other than the key file's own read-only one, or a log line.
- **FR-31** **The write gate.** Every file the bench writes (traces, the report, transcripts, the run log) is written
  through one function that refuses content containing the key's value. The refusal names the file and never prints
  the value; the invocation stops (exit 1), keeping what it had already written. ~~In the vanilla image nothing strips
  secret-shaped variables from the agent's commands, so an agent could print the key there; the gate keeps it out of
  the record, and the provider still sees whatever the agent prints (not_verified).~~ *(Cycle 4 addendum, Item 25
  (b), condition 6: the gate stays. No agent can print the key now, since none holds it, so the gate guards against
  something that should never happen.)*
- **FR-32** A fake-agent run still refuses any API-key-shaped variable (FR-12, no exemption) **and** a set
  `BENCH_KEY_FILE`. CI never has a key. A live run needs `BENCH_KEY_FILE`, except against the stand-in (`--standin`). *(Implement, T045: `BENCH_KEY_FILE` is itself key-shaped under FR-12's rule — `KEY` is one of its parts — and its
  value is a path. A **live** run accepts that one name and still refuses every other key-shaped variable; a fake
  run refuses it with its own message.)* *(Cycle 4 addendum, Item 25 (b), condition 7: fake-agent runs are unchanged,
  and start no relay.)*

**Caps and the plan (P4, P2)**
- **FR-33** Caps: a **turn cap** per run (`BENCH_TURN_CAP`, default 30), a **wall-clock limit** per live run
  (`--run-limit`, default 900 s for live harnesses; the fake agent's stays 300 s) and a **spend cap** per invocation
  (`BENCH_SPEND_CAP_USD`, default 10.00, well under the key's 50 per day). A run that reaches the turn cap or the
  spend cap ends `stopped` (cause `turn-cap`, `spend-cap`). Once the spend cap is reached, every remaining cell is
  recorded `stopped` (`spend-cap`, not started) without a request.
- **FR-34** **The plan comes first.** Before any request, a live run prints its plan: cells (tasks × harnesses ×
  arms), each harness and its pin, the model, the caps, and a spend estimate (an upper bound at the turn cap, and a
  typical figure), computed from the model's price per million tokens (`BENCH_MODEL_PRICE_IN`, `_OUT`, in
  `pins.env`) and per-turn token figures stated in the plan. `--dry-run` prints only the plan, needs neither Docker
  nor a key, and exits 0.
- **FR-35** **Spend is what OpenRouter reports**: each response's `usage.cost` when present, else its generation
  stats (`GET /api/v1/generation?id=…`, asked by the driver after the run). It is recorded in the trace with its
  source; a generation whose cost could not be read is counted and named, never estimated. Spend and tokens appear in
  the report **only** under the appendix, below the table (P6).

**Endings (natural intensity)**
- **FR-36** A fifth ending, **`stopped`**, means the run ended for an infrastructure reason. It carries a cause:
  `api-rate-limit` (429), `api-error` (5xx or a malformed answer), `api-unreachable`, `key-rejected` (401 or 403),
  `harness-exit` (a non-zero exit or a crash), `harness-unresponsive`, `turn-cap`, `spend-cap`, `placement`,
  `transcript-unreadable` or *(Cycle 4 addendum, Item 25 (b))* `model-refused` (the relay refused a request naming a
  model other than the pin). Its reason line names it. A `stopped` row is listed under **Not compared
  (infrastructure)** and is never counted as a loss or a win for either image. A run limit reached while a tool
  call is in flight ends `hung` (the environment's outcome, as in slice 0); reached with no call in flight, it is
  `stopped`, `harness-unresponsive`.
- **FR-37** A missing or refused key file stops the whole invocation before any container starts (FR-29). A key that
  OpenRouter rejects ends that run `stopped` (`key-rejected`), and every later cell is recorded `stopped` without a
  request: the key will not be accepted on the next one either.

**The catalog for a live agent (seam 6)**
- **FR-38** Each task's goal is in plain words, the same in every arm and harness, and is the live prompt. Completion
  is the driver's check, never the agent's claim (cross-stack P004). Each task keeps its fake-agent policy for CI.
- **FR-39** One task is added, `python-missing-module`: a script imports a module neither image has, and the goal is
  its output in a file. Live, it can produce **module not found** and **network denial** (an install attempt with no
  network), which no slice-0 task can. Command not found and memory kill have no live task; the probe produces them
  (FR-43). *(Amended at implement, T052, declared: the install is a plain `pip install`, because 007's FR-28 forbids the flag
  that overrides an externally managed interpreter anywhere in the repository. So the install fails differently per
  image: vanilla's pip refuses at once (externally managed: `other`), and timelike's goes through the package guard,
  which finds no registry (`network denial`). The probe produces network denial in both images.)*

**Failure categories (SC-7)**
- **FR-40** Every failed call (a non-zero exit, or a hang) carries **exactly one** category, decided in this order from
  its exit code, its hang flag, its output head and the container's OOM count:
  1. `timeout`: the call hung (the bench's limit or the harness's own), or exited 124, or carries 003's verdict
     `(timeout after …)`;
  2. `memory-kill`: exited 137 (or carries 003's `(out of memory: …)`) **and** the container's `memory.events`
     `oom_kill` count rose; 137 without that evidence is `other`;
  3. `command-not-found`: exited 127, or its output carries `command not found` (the shells' and 007's messages);
  4. `module-not-found`: `ModuleNotFoundError`, `No module named`, `Cannot find module`, `ERR_MODULE_NOT_FOUND`;
  5. `network-denial`: connection refused or unreachable, a DNS failure, Adele's denial verdict, or the package
     guard's `unreachable`;
  6. `other`, shown and never dropped.
- **FR-41** A network denial is from **the task container**, and the report says so (cross-stack P001).
- **FR-42** The report has a category table per harness: categories × arms, `other` included.
- **FR-43** `timelike-bench categories --probe` starts a task container of each image (`--network none`, a 64 MiB
  memory limit), runs one real failing command per category in it, and prints each command with its category and
  the evidence. It is how the tests produce every category in both images (P005).

**Parsing a harness's output (seam 8)**
- **FR-44** Each live harness has a parser that reads turns, calls, commands, exit codes and output sizes from the
  harness's own output: OpenCode's `--format json` events, and Codex's session rollout file (`--json` on stdout as
  well). A transcript the parser cannot read ends the run `stopped` (`transcript-unreadable`), naming the harness, the
  run and what failed. It is never scored as zero calls.
- **FR-45** The raw transcripts of every live run are kept beside the traces (`transcripts/`), through the write gate.
- **FR-46** The parsers are tested against transcripts recorded from the harnesses themselves (`tests/fixtures/
  transcripts/`), not against output the bench produced (P005, lore `llm-apis` Q001).
- **FR-47** **The model stand-in** (`benchlib/standin.py`, timelike's own code) speaks OpenAI chat completions and the
  Responses API, answering each task with scripted tool calls. `--standin` runs the whole live path (harness image,
  placement, relay, parsers, report) against it with no key; the transcripts of FR-46 are recorded with it.

**The verdict (SC-6; revision 8)**
- **FR-48** A comparison between two arms of one task under one harness compares, in order: **ending** (`completed` >
  `escalated` > `failed` > `hung`), **turns**, **hangs**, **failed commands** (non-zero exits, a hung call
  included), each fewer-wins; equal on all four is a tie. Each call is counted once per row: a hung call is one failed
  command and one hang. Wall-clock and tool calls are reported and never decide. The verdict sentence quotes only
  counts that appear in the table. A comparison with a `stopped` side is not made.
- **FR-49** Within a harness, a task's block shows the three arms in one table and two verdicts (not told against
  vanilla, told against vanilla). A task is listed under the worse of its two verdicts, so a loss is never hidden by
  a win (P6).

**The live run for the mentor**
- **FR-50** `make bench-live` runs the whole catalog under both live harnesses in all three arms, n = 1, labelled so,
  with `BENCH_KEY_FILE` set. `make bench-live DRY_RUN=1` prints the plan only. The quickstart names the variables,
  their defaults, the estimate and where the report and traces land.

### Edge cases (slice 1)

- **OpenRouter answers 429 or 5xx.** Each harness retries on its own; the relay records every status. If the run then
  ends without a check passing, and the relay saw only errors for its last request, it ends `stopped`
  (`api-rate-limit` or `api-error`).
- **The harness hangs, with no call in flight.** The run limit stops it (`stopped`, `harness-unresponsive`).
- **The harness's reported version differs from the pin.** The run is refused (FR-23).
- **A key-shaped string in a transcript that is not the key.** Not refused: the gate matches the key's value only.
- **A timelike tool name inside an argument** (`echo run`). Not counted: only command words count (FR-19).
- *(Cycle 4 addendum)* **An agent's command calls the relay itself** (`curl http://bench-relay:8417/...`). It is
  served or refused by the same rules as the harness, counted toward the same caps, and not told apart (FR-26).
- *(Cycle 4 addendum)* **A task's setup is slow.** Setup and check are the bench's own steps, not the agent's calls,
  so they run under the bench's step limit (120 s), not the agent's call limit (lane 02s1-a, item 2). A told run whose
  setup fails records its placement as `not placed`, since the placement comes after setup.

### Out of scope (slice 1)

Repetitions and spread, publishing, incident replays (slice 2). Comparing harnesses with each other. A live harness in
CI. Claude Code (FR-21). Any change to the agent or vanilla image.

### Assumptions (slice 1)

10. **Turns, per harness.** OpenCode's turn is a `step_start`…`step_finish` pair; Codex's is a model response, bounded
    by its `token_usage_record`. A call's turn is the response that issued it, and a run's turns are the last such
    turn (slice 0's rule). The two are not comparable with each other, which is why harnesses are never compared.
11. **Output heads, per harness.** Both live harnesses report a call's output with stdout and stderr merged. The
    trace's `stderr_head` holds that merged head for a live call, and the trace says so (`output_streams: merged`).
