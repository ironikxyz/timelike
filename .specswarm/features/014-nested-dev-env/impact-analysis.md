# Impact Analysis: Modification to Feature 014

**Modification:** revision 17's refusal code (exit 4 → exit 2) for forbidden settings, plus the seams decided ·
**Analysis date:** 2026-10-17T04:04:44Z (read from the clock)

## Affected components

| Component | Impact | Notes |
|---|---|---|
| `spec.md` | High | FR-8, Scenario 2, criterion 3, D-1, D-7 rewritten; the struck criterion stays struck |
| `plan.md`, `research.md` R3/R4, `contracts/adele-env.md`, `data-model.md`, `tasks.md` | Medium | refusal path: HTTP 422, exit 2 (setting) or 3 (image, provisional) |
| agentio (001) | None | exit 2 is agentio's existing usage error; no change to 001's contract, and its § Confirmation clause is carried, not edited |
| 12's ledger and `status` | Low | a setting refusal is a `refused` row with an empty `extend`; status prints "operator's command: none" |

**Built code affected:** none. Only the spec, plan and tasks existed, and the uncommitted beginnings of T001–T002,
which do not touch refusals.

**Risk:** low. **Proceed:** yes.

## Cycle 6 — slice 1 (`bridge/sends/13-rev17-20261018-120700.md`), analysed 2026-10-18T12:17:01Z (read from the clock)

| Component | Impact | Notes |
|---|---|---|
| `adele/cmd/adeled` (`resolve`, a new `context`, `serve`) | High | the sandbox gains devcontainer parsing and translation, build-context archiving and the Dockerfile scan; serve wires collection into the reaper's tick |
| `adele/internal/compose` | High | `build:` allowed with its own refusals; labels for session, grant, requester, one-shot and devcontainer settings; the model hash covers a build's context digest |
| `adele/internal/engine` | High | builds (streamed context, classic builder, pull watch), exec (attached, bounded), images in `Down` and `Count`, the requester's container by address, attach for the context sandbox |
| `adele/internal/broker` (`env.go`, `http.go`, `broker.go`) | High | builds and lifecycle in `up`; `exec`; `collect`; `/v1/sessions/end`; the peer address passed in |
| `adele/internal/ledger` | Medium | one writer for a performed row with no undo and no expiry; the live queries exclude rows with no expiry |
| `adele/internal/reaper` | Low | a collection hook on its tick |
| `tools/bin/adele` | High | `env exec`, `env collect`, `session end`; readiness per decision C; the verdicts |
| agentio (001), 03's `run` | None | exec's output and bound follow their contracts; nothing in them changes |
| 004's grants and ledger | Low | `instances` and `live` exclude exec and session-end rows (no expiry); `adeled ledger` prints them as it prints any row |
| `tests/run.sh`, `tests/e2e/lane.conf`, `tests/e2e/nested.bash` | Medium | the lane-start image sweep; the new files' classes; helpers for images and labels |
| slice 0's e2e cells | Low | the bring-up cells' "ready (running)" assertions for a portless service, if any, move to decision C's words |
| README | Medium | the `adele env` section, the readiness paragraph, the status block (only if both slice-1 criteria are met), the reference |

**Risks:**
- **The classic builder.** It is the only builder the build API offers without a BuildKit session, and the host's
  engine must still provide it. Not verifiable here (no Docker); the lane's first build cell says.
- **A base image that disappears between the check and the build** would be pulled by the classic builder. Adele
  watches the build's progress and cancels it at the first pull message (R15).
- **No exec kill in the Engine API.** Exec's bound concludes the call, but cannot stop the process. The verdict says
  so, and `down` removes the container.
- **The disk-bound host** (cross-stack P006): build fixtures are a few layers.

**Proceed:** yes.
