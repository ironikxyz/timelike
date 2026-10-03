# Timelike — Code Instance

This is the **implementation** instance of the Timelike mentored project. It uses SpecSwarm to build features from spec-ready prompts.

## Directory Context

```
../                      ← mentor root (orchestration)
../plan/                 ← plan instance (discovery — separate Claude)
./                       ← you are here (code/)
├── .specswarm/
│   ├── constitution.md  ← project governance (includes WHY principles from discovery)
│   ├── tech-stack.md    ← approved technologies (from /mentor:stack)
│   └── features/        ← built features
└── CLAUDE.md            ← this file
../bridge/               ← mentor-managed handoff
    ├── active-prompt.md ← current feature to build (read this)
    └── feedback/        ← implementation learnings (mentor routes these)
```

## Rules

1. **Build from `../bridge/active-prompt.md`** when it exists. This is your feature spec.
2. **Use the SpecSwarm sequence the send prescribes:** `/specswarm:specify --from-send <send>` (new
   feature, on a fresh `NNN-slug` branch) or `/specswarm:modify --from-send <send>` (a feature with
   history, on a `modify/NNN-*` branch), then `/specswarm:plan` → `/specswarm:tasks` →
   `/specswarm:implement`, then `/specswarm:ship` after the mentor's sign-off. **Never run
   `/specswarm:build` on this project:** under specswarm ≤ 2.20.0 its Stop hook blocks forever on this
   project's `unknown` quality score (specswarm's 2.21.0 note, relayed by the mentor 2026-10-01).
3. **Never modify `../bridge/` or `../plan/`.** Only write to `./` (this directory).
4. **Report implementation learnings** to the mentor (return to root, run `/mentor:feedback`).

## Workflow

1. Check `../bridge/active-prompt.md` for the current feature to build
2. If it exists, read it — it contains:
   - WHY context (principles, vision)
   - Feature description
   - Constraints (from principles and environment)
   - Acceptance criteria
   - Dependencies
   - Stack context (recommended technologies)
3. Run `/specswarm:init` if `.specswarm/constitution.md` doesn't exist yet
4. Run the sequence in rule 2 with the send's archived path under `../bridge/sends/` (the send names
   it in its `--from-send` line; its `> Source:` line names the prompt, not the send) — not
   `/specswarm:build`
5. When done, return to mentor root for next steps

## Stack Guidance

When running `/specswarm:init`, read **`../bridge/governance-context.md`**. It carries the discovery
revision on a `> Discovery:` line — which is what seeds `governance_audited_against` — plus the stack
recommendation and the governing principles.

**Not `../bridge/active-prompt.md`**: init runs before any feature is sent, so no active prompt exists
yet. And not `plan/` directly — reading across the boundary is what the three-instance split exists to
prevent.

The recommended stack was chosen based on:
- Project constraints and principles from discovery
- Claude's build competence (Tier 1 technologies preferred)
- Technology capability mapping

## Dispatch Mode

When `../bridge/dispatch/code-track.md` exists and you're told to process it:

1. Read the full `code-track.md` header (principles, stack context, execution config)
2. For each prompt in order, run the sequence below. **Do not use `/specswarm:build`** — it does not
   accept `--dispatch`, never forwards it, and blocks on `Press Enter to start`:

   ```
   git checkout -b [NNN]-[slug]          # or check out the existing branch
   /specswarm:specify   "[NN] [short name]" --from-send bridge/sends/[NN]-rev[M]-[TIMESTAMP].md
   /specswarm:plan
   /specswarm:tasks
   /specswarm:implement --dispatch
   ```

   The `--from-send` path is the prompt block's `Send:` line, copied exactly — a bare relative path
   resolves against the project root, where `bridge/sends/` lives. The quoted text is only a short name
   for the slug: the send's content is the feature description, and the mailbox is never read. Requires
   **specswarm ≥ 2.9.0** (the BotBaubble series number, as every version claim here is written); if the flag is unknown to the installed copy, drop it and
   write the `provenance.md` sidecar the code track describes instead.

   Create the branch **first**: `/specswarm:specify` reuses a branch already named `NNN-slug` and skips
   its confirmation prompt. Without it, specify takes the standalone path and blocks asking whether the
   branch is correct. `/specswarm:clarify` is skipped on purpose — every question it asks is interactive,
   so there is nothing to suppress.
3. **Between features**: re-read `code-track.md` header for feature-level re-grounding
4. **Within features**: hardened implement handles task-level re-grounding via decisions.md
5. **When something needs a human, write a pause file and stop** — never present a question, because
   nobody is reading and every later prompt is stranded behind it. Three causes:
   - a low-confidence FLAGGED decision (implement does this for you)
   - `[NEEDS CLARIFICATION]` markers surviving specify's validation — resolve by informed guess and log
     each as a decision with its confidence; pause only if low
   - a technology conflict found by `plan` against `tech-stack.md` — a human call by definition
   - **a FLAGGED decision touching a file outside the feature's `tasks.md` scope.** This one needs no
     self-assessment, which is the point: the confidence label has never once been recorded as `low`
     across 705 labelled decisions on this machine, so it cannot be the only trigger. A wrong call inside a feature's scope is
     a bad feature; outside it, a bad repository

   Write it to `../bridge/dispatch/pause-[NN].md` so the mentor side finds it. Note that implement's own
   pause file lands at `bridge/dispatch/…` relative to **this** repo, i.e. `code/bridge/dispatch/` —
   the mentor checks both locations, but prefer the `../bridge/` path when you write one yourself.
6. After each feature completes, check for `.implement-complete` marker in the feature directory
7. **Append a cycle report** to `.specswarm/features/[NNN]-[slug]/cycle-report.md` — **this path, and
   not any other this file may name elsewhere; a send's cycle-report path supersedes a project
   convention, and the mentor reads only this one** — one section per
   cycle, headed `## Cycle [N] — [the send's archived path]`, append-only, never overwritten. A cycle is
   one instruction (one archived send) built to acceptance, so a later `--regenerate` or
   `/specswarm:modify` appends a further section. Three groups: **cite** the `.implement-complete` fields
   (only where the cycle ran under `--dispatch`, which is the only mode that writes that marker —
   otherwise write `Group A: not applicable — no marker on this path` once, never eight absences;
   naming the marker path — never copy a measured number, and give each field one of `present`,
   `absent` or `not looked for`, per field always: an aggregate the mentor cannot check field-by-field
   against the marker is read as a disagreement), **copy** `source_send`, `source_prompt`, `prompt_revision`, `discovery_revision` and `slice`
   from the send, and **write** what only you can know: `delegations` (an empty list is a result),
   `criteria_reestablished` (cite each as `NN · "distinguishing text"` — there are no criterion IDs —
   with a mode of `executed [test]`, `observed by [who]` or `unconfirmed`; `unconfirmed` is the right
   answer for a Manual criterion nobody looked at, and beats omitting it), `reconcile_mode`
   (`full` | `scoped`), `not_verified`, `changed_other_features`, `process_failures_recorded`,
   `retired_prompts_seen`. **Do not write `demo_points_reached`** — the mentor derives demo points from
   your citations and their modes. The send carries the same list; its long form is in
   `/mentor:dispatch`. **The mentor reads this file and never writes into it**, so a field you leave out
   stays out and is reported as absent.
8. Do NOT modify `../bridge/` — only read from it, and write pause files. The mentor manages dispatch state.

**Important**: `--dispatch` suppresses user-interaction prompts, downgrades checklist failures to
warnings, skips the git-workflow step and its merge question, and commits per task (no final bulk
commit). It does **not** make the other commands in the sequence non-interactive — that is what the
branch-first rule and the pause rules above are for.

## Implementation Notes

- Each feature prompt traces back to discovery principles — honor the WHY
- Acceptance criteria are outcome-grounded, not just "tests pass"
- If you encounter a missing constraint or principle gap during implementation, note it — the mentor will route it back to plan/ if needed
- **When you raise a question for the mentor, raise it somewhere with a stable path** — a
  `../bridge/feedback/` file, or a named item in your own carry-forward register. A question asked only
  in passing has no arrival signal, and the mentor now enumerates inbound artifacts by path and age
- **An answer will come back beside the question**, not in the next send. Check the feedback file you
  raised it in; a send is a build instruction for one cycle and the next one overwrites it
- **When an item you raised is answered, close it in your own register.** An answer written elsewhere
  leaves your item open regardless — that is how one answered question sat open for four days
- Built features appear in `.specswarm/features/NNN-slug/` per SpecSwarm convention
