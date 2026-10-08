---
governance_audited_against: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
---

> **Amended 2026-09-28** per `../bridge/feedback/stack-review-2026-09-28.md` (plan's review of
> the choices made at init). This is not a discovery revision, so `governance_audited_against` is unchanged.
> Changed: C1, the Python type checker is now `mypy --strict`.
>
> **Amended 2026-09-28** to match the init template shipped in specswarm 2.10.1 and the parsers
> that read this file. Content was unchanged except for how prohibitions were marked.
>
> **Amended 2026-09-28** for specswarm 2.11.0, whose single parser (`lib/tech-stack-parser.sh`)
> matches technology names exactly. Every approved technology is now a `- **Name** version` bullet,
> which is the shape the parser reads. Policy text is numbered or in prose, so the parser does not
> read it as a technology. The cgo SQLite driver and cgo are marked prohibited again, now that
> marking them no longer prohibits Go and SQLite. The stack itself is unchanged. This is not a
> discovery revision, so `governance_audited_against` is unchanged.
>
> **Audited against discovery revision 3** (2026-09-28), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 06:26:58Z). Added: the security-scanning row (govulncheck, pip-audit, Syft +
> Grype, gitleaks, all pinned) and Adele's image built `FROM scratch` or distroless static. The
> struck soft constraint (static single binaries for hot-path tools) changes nothing here. Revision
> 3 is appended to `governance_audited_against`.
>
> **Audited against discovery revision 4** (2026-09-28), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 06:40:04Z). No change needed: revision 4 clarifies a policy clause on
> exemptions, not a technology choice, and `stack.md` did not change. Revision 4 is appended to
> `governance_audited_against`.
>
> **Audited against discovery revision 5** (2026-09-28), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 13:13:20Z) and `stack.md` as amended at plan `d606ed1`. Amended: Python is
> pinned to the current stable 3.14.x (CVE-2026-82049 is fixed only from 3.14, and revision 5 counts
> a stable fix on another minor line as available); the constraint "3.12+" is unchanged. Added
> notes 6 (no `openssh-client` in the agent image, stack note 15) and 7 (base-image re-evaluation
> trigger, stack note 16). Revision 5 is appended to `governance_audited_against`.
>
> **Audited against discovery revision 6** (2026-09-28), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 23:08:03Z), § "What Changed In Those Revisions". No change needed: revision 6
> clarifies output-contract rules 2 and 3, a policy on tools' output, not a technology choice, and
> `stack.md` is unchanged (0 lines). Revision 6 is appended to `governance_audited_against`.
>
> **Audited against discovery revision 7** (2026-09-30), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 2026-09-29T09:40:34Z), § "What Changed In Those Revisions". No change needed:
> revision 7 adds tension T4 (a project's own checks run, bounded) and rules feature 01's hooks
> default. It is not a technology choice, and `stack.md` is unchanged (0 lines). The one "hook" line
> here (Prohibited 6, a harness-specific hook, P7/T3) is about harness hooks, not repository hooks.
> Revision 7 is appended to `governance_audited_against`.
>
> **Audited against discovery revision 8** (2026-09-30), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 2026-09-30T06:15:21Z), § "What Changed In Those Revisions". **No change
> needed:** revision 8 clarifies tension T4 and adds a Hard constraint on the operator's host git
> state. Neither is a technology choice, and `stack.md` is unchanged (0 lines). Revision 8 is appended
> to `governance_audited_against`: a no-change audit is a recorded result.
>
> **Audited against discovery revision 9** (2026-10-01), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 2026-10-01T04:32:58Z), § "What Changed In Those Revisions". **No change
> needed:** revision 9 clarifies the output contract's exit-code scope (pass-through for a tool that
> runs a command). That is not a technology choice, and `stack.md` is unchanged (0 lines). Revision 9
> is appended to `governance_audited_against`: a no-change audit is a recorded result.
>
> **Audited against discovery revision 10** (2026-10-02), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 2026-10-02T05:50:50Z), § "What Changed In Those Revisions". **No change
> needed:** revision 10 clarifies exit 4's two envelopes (confirmation and grant, told apart by
> `status`). That is a contract shape, not a technology choice, and `stack.md` is unchanged (last
> changed at `d606ed1`, revision 5). Revision 10 is appended to `governance_audited_against`: a
> no-change audit is a recorded result.
>
> **Audited against discovery revision 11** (2026-10-04), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 2026-10-04T00:24:17Z), § "What Changed In Those Revisions", and
> `../bridge/feedback/07-20261003-022613-snapshot-store-and-persistence.md` § Resolution.
> **Amended:** `stack.md`'s Snapshots and P5 rows moved at plan `0f6e1ed` from a git shadow store to
> a Python stdlib content-addressed store (git keeps only modes 644/755, turns nested repositories
> into gitlinks, tracks no empty directories, and its index writes fire feature 01's hook
> dispatcher). The git line said "snapshots, shadow store outside the workspace", which now
> contradicts the stack, so it is amended as plan asked: git stays in the agent image as the agent's
> own version control, and the snapshot store is named under Python. Rule 10's revision (state
> locations) is a contract rule, not a technology choice. Revision 11 is appended to
> `governance_audited_against`.
>
> **Audited against discovery revision 12** (2026-10-04), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 2026-10-04T08:54:45Z), § "What Changed In Those Revisions". **No change
> needed:** revision 12 clarifies the output contract's rule 13 (the line cut applies in JSON too). That
> is a contract rule, not a technology choice, and `stack.md` is unchanged (last changed at `0f6e1ed`,
> revision 11). Revision 12 is appended to `governance_audited_against`: a no-change audit is a recorded
> result.
>
> **Audited against discovery revision 13** (2026-10-05), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 2026-10-04T23:28:30Z), § "What Changed In Those Revisions", and
> `../bridge/feedback/batch-20261004-232148-rule9-scope-and-workspace-context-file.md` § Resolution.
> **No change needed:** revision 13 clarifies the output contract's rule 9 (which changes are
> confirmed). That is a contract rule, not a technology choice, and `stack.md` is unchanged. Revision
> 13 is appended to `governance_audited_against`: a no-change audit is a recorded result.
>
> **Audited against discovery revision 14** (2026-10-08), via `../bridge/governance-context.md`
> (`/mentor:regovern` for revision 14), § "What Changed In Those Revisions" (relied on), and
> `../bridge/feedback/04-20261008-173021-agent-runtimes-for-package-installs.md` § Resolution (Q1–Q3).
> **Amended (1.3.1 → 1.4.0):** revision 14 struck discovery's PEP 668 clause on the base image and added
> stack.md's *Agent runtimes* row. Checked here: the Python language note (it said timelike's tools never use
> "the system Python (PEP 668 externally managed)"; the slim image has no system Python, and the agent now
> has its own interpreter), uv's note ("also the default for the agent's own installs"; installs now go
> through the agent interpreter's own pip, configured to the user location), Platform and Services (no
> agent runtime was listed), and Version Updates (pins). Changed: a new *Agent runtimes* entry under Build
> Tool (agent Python, Node), the Python note, uv's note, the Debian note, and Version Updates item 1.
> Unchanged: prohibition 3 (timelike's tools still never use an agent interpreter or venv), the
> prohibited list, the scanners. Revision 14 is appended to `governance_audited_against`.

# Tech Stack - Timelike

**Version**: 1.4.0
**Last Updated**: 2026-10-08
**Auto-Generated**: No. Derived from `../bridge/governance-context.md` (stack option A, discovery
revision 2; audited against revisions 3 to 11, per the notes above)

The language boundary follows P4. Everything the agent runs inside its environment is Python (plus
Bash for the environment layer). The one component that reaches beyond it, Adele, is Go.

---

## Core Technologies

### Framework

No application framework: stdlib-first by design (H5). Agent-side tools are single-file Python
scripts. Adele uses Go's `net/http` and `httputil.ReverseProxy`, which handles Docker exec/attach
stream upgrades.

### Language
- **Python** 3.12+ (agent-side tools and the shared `agentio` output-contract module)
  - Notes: pinned to the current stable 3.14.x in `pins.env` (discovery revision 5, H9's "fix
    available"). uv-managed CPython at `/opt/timelike/python`, always run with `-I`, never the agent's
    interpreter (Agent runtimes, below) or an agent venv. Fully annotated, `mypy --strict`
    *(Revised, discovery revision 14: it said "never the system Python (PEP 668 externally managed)";
    the slim image carries no system Python.)*
  - Snapshots (feature 07; discovery revision 11, replacing a git shadow store): a stdlib
    content-addressed store outside the workspace. Blobs are deduplicated by content across
    snapshots, symlinks are stored as links, and it lives in the per-workspace state root from
    07 slice 1
- **Go** 1.23+ (Adele only)
  - Notes: `CGO_ENABLED=0`, static binary
- **Bash** 5.x (environment layer)
  - Notes: Dockerfile `ENV`, `BASH_ENV` and system gitconfig, so defaults reach non-interactive
    `bash -c` and `bash -lc`. rc files and `PROMPT_COMMAND` alone do not

### Build Tool
- **Docker** (image build and runtime)
  - Notes: the build stamps the git revision into the image label and `timelike --agent-info` (H8).
    Adele's image is built `FROM scratch` or distroless static, so it carries almost no OS
    packages (H9)
- **Docker Compose** v2 (agent image plus the Adele sidecar)
  - Notes: nothing is installed on the host
- **Debian** (agent image base, trixie-slim at a pinned digest)
  - Notes: minimal. No `openssh-client` (note 6). The base is re-evaluated at slice 1 (note 7). It carries
    no system Python (discovery revision 14)
- **uv** (pinned version; Python interpreter and installs)
  - Notes: provisions timelike's interpreter and the agent's (below). `--exclude-newer` backs the package
    guard. *(Revised, discovery revision 14: it said "also the default for the agent's own installs";
    the agent's bare `pip install` now goes through the agent interpreter's own pip, to the user location.)*
- **Agent runtimes** (discovery revision 14, stack.md *Agent runtimes*): for the agent, never for
  timelike's tools
  - Agent Python: uv-managed CPython at the same pinned 3.14.x as timelike's, in its own prefix (not
    `/opt/timelike/python`). Provisioned without its `EXTERNALLY-MANAGED` marker; its own `pip.conf` sets
    `[install] user = true`. `python3`, `python`, `pip`, `pip3` on the agent's `PATH`
  - Node: the official release tarball of the current Active LTS, pinned by version and SHA-256 in
    `pins.env` and verified at build. Its own `etc/npmrc` sets `prefix` under the agent's home. `node`,
    `npm`, `npx` on the agent's `PATH`
  - `~/.local/bin` on `PATH` (the `ENV` block and profile.d). Never `PIP_BREAK_SYSTEM_PACKAGES`, and no
    wrapper around `pip` or `npm` (feature 15 sits in front of them later)
  - The bench's vanilla image carries the same binaries with stock behaviour (marker kept, npm's default
    prefix, no timelike configuration). Both images are scanned like everything else
- **Node** (agent runtime, current Active LTS; the Agent runtimes entry above)
  - Notes: named on its own line so the tech-stack parser reads it as approved; never used by timelike's
    tools

### Platform and Services
- **ripgrep** (structural search; invoked and wrapped, not written)
- **fd** (structural search)
- **ast-grep** (structural search)
- **universal-ctags** (structural search)
- **tree-sitter** (structural search, CLI)
- **jq** (structural search)
- **tmux** (interactive services, private socket)
  - Notes: with setsid/killpg and `/proc` for service control
- **cgroup** v2 (resource budgets)
  - Notes: `memory.max`, `memory.events`, `cpu.max`, `pids.max` are the source of truth for budget
    verdicts
- **git** 2.40+ (in the agent image: the agent's own version control, with feature 01's hook
  dispatcher and system gitconfig)
  - Notes: not the snapshot store (discovery revision 11). Feature 07's snapshots use the Python
    stdlib content-addressed store (see Python), which runs no git command and never touches the
    project's own `.git`
- **fly.io** (provider, slice 0; Machines REST API v1)
  - Notes: called only by Adele. Per-app deploy token with explicit expiry
- **Playwright** (web verification, slice 2; optional image layer)
- **Chromium** (pinned, with Playwright)

---

## State Management
- **SQLite** 3.x (Adele's ledger, grants cache and spend meter)
  - Notes: owned only by Adele's container. The agent image cannot read it (H1)
- **modernc.org/sqlite** (pure-Go SQLite driver; see note 1)

There is no application state library, because there is no user-facing GUI.

---

## Styling

Not applicable: there is no user-facing GUI, and the constitution has no UX section.

---

## Testing

### Unit Testing
- **pytest** (Python unit tests)
- **go test** (Adele unit tests)

### Integration Testing

`go test` runs against the real Docker Engine API version in use and the real fly.io Machines API,
and pytest covers tool-level integration. Adele's Docker filter and provider calls are never mocked
to reach coverage.

### End-to-End Testing
- **bats-core** (run inside the image)
  - Notes: one test per acceptance criterion, named after its distinguishing text. Each
    environment default is tested under `bash -c`, `bash -lc` and an interactive shell

---

## Quality Tooling

Added at init to enforce H8. These are not in the stack recommendation; plan accepted them in its
review.

- **ruff** (Python lint and format)
- **mypy** (Python type checking, `--strict`)
  - Notes: runs in Python, which fits stdlib-only tools; pyright was rejected because it needs Node
- **go vet** (Go static checks)
- **gofmt** (Go formatting)
- **staticcheck** (Go lint)
- **shellcheck** (Bash lint)
- **coverage.py** (Python coverage; Go uses `go test -cover`)


### Security Scanning

Merge gate from discovery revision 3 (H9). All pinned.

- **govulncheck** (Go; reports only vulnerabilities reachable from Adele's call graph)
- **pip-audit** (Python dependencies and tooling)
- **Syft** (SBOM of both images)
- **Grype** (vulnerabilities in the Syft SBOM, including both images' OS packages)
- **gitleaks** (committed secrets)
  - Notes: shares its rule set with `run`'s output redaction (feature 03)

---

## Approved Libraries

Both languages are **stdlib only** by default. Go additionally has the SQLite driver above. Any
addition needs justification in the feature plan and an entry here.

---

## Prohibited Technologies

The following technologies are **NOT** approved for this project:

- ❌ mattn/go-sqlite3 (use modernc.org/sqlite instead)
- ❌ cgo (use pure-Go packages instead)
- ❌ MCP (use plain shell commands instead)
- ❌ pyright (use mypy instead)

### Not permitted (policy, enforced by review, the constitution and the gates)

These describe patterns, not technologies, so they are numbered and the parser does not read them.

1. LLM calls in any deterministic tier (P7, H6)
2. Daemons inside agent-side tools (H6)
3. The system interpreter or an agent venv for timelike's own tools (H5)
4. The Docker socket, Adele's volume or its credentials reachable from the agent image (P4, H1)
5. `sudo` or any other privilege escalation inside the agent image. Left unmarked, so that tasks
   enforcing P4 can say "sudo" without a warning
6. A harness-specific hook as the only way a capability works (P7, T3)
7. Provider access other than the Machines REST API through Adele
8. Anything installed on the host outside containers

---

## Guidelines

### Adding New Dependencies

Before adding a new dependency:
1. Check whether the standard library or an approved library already solves the problem (H5)
2. Verify the library is actively maintained, and that its licence is MIT-compatible
3. Check the image-size and start-up impact (start-up budget in `quality-standards.md`)
4. For Adele: confirm it builds with `CGO_ENABLED=0`
5. Justify it in the feature plan and add it here as `- **Name** version (purpose)`

### Version Updates

1. Pin the base image digest, uv, the Python interpreter, Node (version and SHA-256; discovery revision 14)
   and Chromium. Bump them deliberately
2. Test thoroughly before updating major versions, including against the Docker Engine API version
   in use
3. Document breaking changes in this file

---

## Notes

1. `CGO_ENABLED=0` and SQLite together require a pure-Go driver. The common cgo driver breaks the
   static build. The stack recommendation named SQLite and a static build but not the driver. This
   file resolved that with `modernc.org/sqlite`, and plan's `stack.md` now names the same driver.
   `ncruces/go-sqlite3` (WebAssembly via wazero) is the only other pure-Go option; it has no
   advantage here.
2. Docker daemon access is root on the host. Only Adele holds the socket. Bind-mount sources
   resolve on the daemon's host, hence the same-absolute-path workspace rule. The shared
   workspace volume uses aligned uids and a default ACL.
3. Recheck the GLiNER checkpoint licence (MIT compatibility) before feature 16.
4. Created by `/specswarm:init`. `/specswarm:plan` adds technologies here as features justify
   them and bumps **Version** when it does (provenance preserved verbatim on such edits).
5. Format contract (specswarm 2.11.0, `lib/tech-stack-parser.sh`). The parser reads a technology
   name from every top-level `-` or `*` bullet: an unmarked bullet counts as approved, and a bullet
   with the cross mark counts as prohibited. Names are compared exactly, ignoring case, after
   stripping `**`, a trailing version token and any parenthetical. So write each technology as
   `- **Name** version (purpose)`, and keep policy text out of top-level bullets. From 2.12.0 only
   sections above `## Prohibited` are read as approved, and prose after the version defeats the
   name, so any purpose goes in parentheses.
6. Keep the agent image minimal (stack note 15, discovery revision 5). `openssh-client` is not
   installed unless an acceptance criterion needs it: under P4 the agent holds no SSH keys, and
   credentialed git goes over https through Adele. `git` and its libcurl stay, because https fetch
   is essential to P1. Unfixable findings they carry go into the H9 baseline.
7. A Wolfi/Chainguard-style base image is re-evaluated at slice 1 if baseline review churn exceeds
   one digest move per month (stack note 16). Not adopted now.

---

**Tech Stack Enforcement**: This file is used by SpecSwarm to prevent technology drift. Commands like
`/specswarm:build` and `/specswarm:implement` will reference this file to ensure consistency across
features.
