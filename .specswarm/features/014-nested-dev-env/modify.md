# Modification: Feature 014 — nested dev environments (declared by the re-send)

**Status:** Active · **Created:** 2026-10-17T04:04:44Z (read from the clock) · **Send:** `bridge/sends/13-rev17-20261017-035606.md`
(prompt revision 17, discovery revision 17) · **Original spec:** `spec.md`, written from
`bridge/sends/13-rev8-20261017-012727.md` (prompt revision 8) · **Impact analysis:** `impact-analysis.md`

## Why this cycle corrects in place

Revision 17 **amended** one slice-0 criterion. The forbidden-settings refusal was exit 4 naming the setting; it is
now exit 2 with rule 14's error, naming the setting and stating that no grant allows it, with no operator's
command. By modify's own table that is SUPERSEDED, which would mean regenerating the body. **The re-send declares
otherwise:** "Correct it in place with this modify cycle, declared … Do not regenerate." Only the spec existed when
it was written (plus, since then, plan and tasks, which this cycle updates), so nothing built rests on the false
sentence. The correction follows the re-send.

## Changes

- **F001, the forbidden-settings criterion and FR-8:** exit 4 with a grant envelope becomes exit 2 with rule 14's
  error, with no envelope on stdout and no operator's command. The struck criterion stays visible, struck, beside
  its replacement.
- **F002, the seams:** each proposed decision becomes decided, citing
  `../bridge/feedback/13-20261017-034920-item-27-seams-answered.md` (done before the re-send arrived; checked
  against it).
- **F003, a missing image:** the re-send asks for plan's test. It fails three of the four fields, so FOR-MENTOR
  Item 29 is raised, and exit 3 is built provisionally.
- **Provenance:** revision 17 is appended to `audited_against` (scoped: revision 17's change, the only change to
  prompt 13 since revision 8). `prompt_revision` stays 8.

**Breaking changes:** none to any built feature. Nothing past the spec existed when revision 17 landed.

## Cycle 6 — `bridge/sends/13-rev17-20261018-120700.md` (slice 1, natural)

**Created:** 2026-10-18T12:17:01Z (read from the clock) · **Branch:** `modify/014-slice-1` from `master` at `08df8e2` (slice 0,
v0.22.0) · **Provenance:** modify's row 4. Revision 17 is already in `audited_against`, and neither prompt 13 nor
discovery moved since slice 0's send, so nothing is appended. Slice 1's criteria were in the prompt from generation:
the body is not false (not SUPERSEDED), and this cycle brings them into scope. `prompt_revision` stays 8.

**Why it changes:** the send's slice 1. The operator decided Item 28 (builds) and what ends a session
(`../bridge/feedback/13-20261018-120700-item-28-builds-and-session-end.md`), and gave decision C at slice 0's
sign-off (a one-shot is never ready while it runs).

**Changes:**
- **F004, devcontainers** (FR-16–FR-19, D-9): parsed as JSONC and translated into a compose model in the sandbox,
  then checked and brought up as a compose project. Lifecycle commands run in the container, bounded and named.
- **F005, builds** (FR-20–FR-24, D-8): the sandbox archives each context; Adele streams it to the daemon's build API
  unopened; nothing is pulled; the refusals; the image labelled, tagged under the environment and removed by `down`;
  a bound. slice 0's `build:` refusal (D-7) is lifted, and its remediation text goes.
- **F006, `adele env exec`** (FR-25, D-14).
- **F007, labels, session end and collection** (FR-26–FR-29, D-10, D-11): session and grant labels on every object;
  the requesting container read from the daemon; `adele session end`; `adele env collect` and the reaper's pass.
- **F008, readiness** (FR-11 corrected, D-13, decision C): a service with no readiness signal is "running, no
  readiness check", never "ready"; a certain one-shot is waited for.
- **F009, the lane:** the lane's start sweeps leftover built images by timelike's labels; build fixtures from images
  the lane already has.

**Contract changes, all additive except one:**
- New: `exec` and `collect` on `docker.compose`; `POST /v1/sessions/end`; `adele env exec|collect`,
  `adele session end`; up's answer gains `requester`, `lifecycle`, `built` and per-service `one_shot` and
  `kind`.
- **The one behaviour change:** `up` no longer reports a running service with no healthcheck and no port as
  "ready". It is "running, no readiness check", and up still exits 0 for it; a certain one-shot is waited for. This
  is decision C's correction. Every e2e assertion pinning the old words is updated in the same task.
- The ledger gains one writer (a performed row with no undo and no expiry, for an exec and a session end). Live
  counts, `instances` and the reaper's due list exclude rows with no expiry. No schema change.

**Breaking changes:** none for a built feature's callers. A compose project with a `build:` now builds where slice 0
refused it, which is the point of the slice.
