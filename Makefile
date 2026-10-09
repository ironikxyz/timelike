# timelike — build, test, lint and scan. Everything that needs Docker runs in pinned containers;
# nothing is installed on the host. Two verification lanes (research.md R10):
#   make test       Docker lane — authoritative for the acceptance criteria
#   make test-host  host lane — advisory: agentio/conform units and the env-layer files

include pins.env
export

SHELL := /bin/bash
GIT_SHA := $(shell git rev-parse HEAD 2>/dev/null)
DIRTY := $(shell git status --porcelain 2>/dev/null | grep -v '^?? tests/out/' | head -1)
PYTHON ?= python3
COMPOSE := docker compose

.PHONY: build up down test test-host lint lint-host scan demo docker-check stamp-check bench bench-images grants

docker-check:
	@docker info >/dev/null 2>&1 || { \
	  echo "error: no Docker daemon reachable (code 1) — run this on a host with Docker, mount the host socket, or set DOCKER_HOST; see .specswarm/features/001-agent-shell-baseline/research.md R10" >&2; \
	  exit 1; }

# H8 / lore cross-stack P003: the image carries the revision it was built from. An empty stamp is a
# failure, and a dirty tree would stamp a revision the image does not match.
stamp-check:
	@test -n "$(GIT_SHA)" || { echo "error: no git revision to stamp (code 1) — build from a git checkout" >&2; exit 1; }
	@if [ -n "$(DIRTY)" ] && [ -z "$(ALLOW_DIRTY)" ]; then \
	  echo "error: working tree is dirty, the stamp $(GIT_SHA) would not describe the image (code 1) — commit first, or set ALLOW_DIRTY=1" >&2; exit 1; fi

# Adele (feature 004, research R3). The operator's grant file is local and git-ignored; this never
# overwrites one that exists. (The canary is generated inside Docker, into a volume, by the compose
# service adele-secret — it never touches the host's disk; spec D-8.)
grants:
	@test -e adele/grants.conf || { cp adele/grants.example.conf adele/grants.conf; echo "wrote adele/grants.conf from adele/grants.example.conf — edit it to change the grants"; }

build: docker-check stamp-check grants
	$(COMPOSE) --profile standin build --build-arg GIT_SHA=$(GIT_SHA)

# The stand-in's profile is on: it is what the D8 demo requests (feature 004). Without it, Adele has no
# capability to broker. `docker compose up` without the profile starts the agent and Adele only.
up: build
	$(COMPOSE) --profile standin up -d --force-recreate

down:
	$(COMPOSE) --profile standin down --remove-orphans

test: docker-check stamp-check
	tests/run.sh

test-host:
	PYTHON="$(PYTHON)" tests/host/run.sh

# Linters run in pinned containers. The uv image is distroless (no shell; research R6), so ruff and
# mypy run through the uv inside the built agent image, on the image's own interpreter.
SHELLCHECK_FILES := image/rootfs/etc/profile.d/00-timelike-path.sh tests/run.sh tests/host/run.sh \
  tests/e2e/run-killed-by-memory-limit-names-limit-and-peak.bats \
  tests/e2e/view-directory-overview-dependency-directory-collapsed-within-budget.bats \
  tests/e2e/announcement-at-most-60-lines-in-each-harness-user-level-context-on-start.bats \
  tests/e2e/announcement-generated-from-manifests-missing-tool-fails.bats \
  tests/e2e/timelike-tools-manifest-json-interactivity-risk-safer-alternative.bats \
  tests/e2e/edit-replacing-text-appearing-once-changes-only-that-text-prints-edited-region.bats \
  tests/e2e/edit-crlf-tab-indented-file-given-lf-and-spaces-preserves-crlf-and-tabs.bats \
  tests/e2e/edit-matches-more-than-once-refused-exit-3-listing-line-numbers.bats \
  tests/e2e/edit-matches-nowhere-refused-exit-3-nearest-candidates.bats \
  tests/e2e/edit-dry-run-prints-unified-diff-file-byte-identical.bats tests/e2e/edit-name-and-manifest.bats \
  image/rootfs/etc/timelike/journal-exit.bash \
  tests/e2e/journal-lists-every-tool-invocation-in-order-with-pointer.bats \
  tests/e2e/journal-shell-commands-outside-tools-with-exit-codes.bats \
  tests/e2e/journal-last-20-entries-of-current-session-bounded.bats \
  tests/e2e/journal-concurrent-agents-separable-by-agent-and-session.bats tests/e2e/journal-name-and-manifest.bats \
  tests/e2e/services-start-with-port-readiness-returns-after-port-accepts.bats \
  tests/e2e/services-start-exits-before-ready-non-zero-died-last-log-lines.bats \
  tests/e2e/services-start-port-held-by-registered-service-refused-naming-holder.bats \
  tests/e2e/services-stop-terminates-every-process-in-its-tree.bats \
  tests/e2e/services-list-state-port-uptime-marks-died.bats tests/e2e/services-name-and-manifest.bats \
  tests/e2e/symbols-outline-fixture-14-definitions-line-ranges-no-bodies.bats \
  tests/e2e/symbols-def-file-and-line-first-exit-3-not-found-under-2s-warm.bats \
  tests/e2e/symbols-callers-3-call-sites-grouped-text-based-header.bats \
  tests/e2e/symbols-dependents-of-changed-file-ranked.bats \
  tests/e2e/symbols-stale-cache-rebuilt-answers-from-new-content.bats tests/e2e/symbols-name-and-manifest.bats \
  tests/e2e/verify-pytest-3-failed-409-passed-file-line-name-assertion-lines.bats \
  tests/e2e/verify-parses-pytest-jest-vitest-go-cargo-unknown-format-falls-back.bats \
  tests/e2e/verify-changed-one-source-file-runs-importing-tests-lints-changed-states-why.bats \
  tests/e2e/verify-changed-no-changes-exits-0-nothing-selected.bats tests/e2e/verify-name-and-manifest.bats \
  tests/fixtures/verify/make-project.sh tests/fixtures/verify/record.sh \
  image/rootfs/opt/timelike/libexec/entrypoint \
  tests/e2e/view-anchor-mode-short-stable-anchor-changes-with-content.bats \
  tests/e2e/view-and-search-slice-1-carried-items.bats tests/e2e/fixtures/bounded-read-slice1.sh \
  tests/e2e/run-full-scratch-or-workspace-names-filesystem-and-free-space.bats \
  tests/e2e/run-secrets-redacted-in-shown-output-and-saved-log.bats \
  tests/host/test_env_layer.sh tests/e2e/helpers.bash scan/scan.sh scripts/demo.sh \
  image/rootfs/etc/profile.d/10-timelike-shell-env.sh image/rootfs/etc/timelike/shell-env.bash \
  tests/host/test_shell_env_hook.sh tests/e2e/container-derived-defaults.bats \
  tests/e2e/hooks-a-repository-configures-run.bats tests/e2e/hook-past-its-time-limit-is-killed.bats \
  tests/e2e/hooks-under-env-i-default-bounded-local-unbounded.bats \
  tests/e2e/adele-starts-with-agent-reached-only-through-request-interface.bats \
  tests/e2e/adele-rejects-malformed-grant-with-line-at-fault.bats \
  tests/e2e/request-within-grant-performed-beyond-exits-4-nothing-performed.bats \
  tests/e2e/no-credential-held-by-adele-appears-in-agent.bats \
  tests/e2e/every-performed-request-recorded-in-ledger.bats \
  tests/e2e/adele-isolation-grant-file-and-extend-unreachable-from-agent.bats \
  tests/e2e/fixtures/recover-repo.sh \
  tests/e2e/snapshot-records-tracked-untracked-and-ignored-files.bats \
  tests/e2e/restore-returns-captured-content-and-removes-files-created-after.bats \
  tests/e2e/version-control-history-index-and-stash-unchanged-by-snapshot-and-restore.bats \
  tests/e2e/snapshot-over-the-size-cap-is-partial-and-names-what-was-excluded.bats \
  tests/e2e/snapshot-refuses-home-root-and-their-ancestors.bats \
  tests/e2e/fixtures/bounded-read.sh \
  tests/e2e/view-412-line-file-shows-lines-1-120-with-header-and-next-range.bats \
  tests/e2e/view-range-context-missing-file-and-binary.bats \
  tests/e2e/search-262-matches-shows-50-grouped-with-212-omitted-and-narrowing.bats \
  tests/e2e/search-zero-matches-exits-0-and-1-only-in-strict-mode.bats \
  tests/e2e/view-and-search-resolve-once-and-pass-conform.bats \
  bench/run.sh
PY_IN_IMAGE := docker run --rm -v "$(CURDIR)":/src:ro -w /src -e HOME=/tmp -e UV_CACHE_DIR=/tmp/uv \
  -e UV_TOOL_DIR=/tmp/uv-tools --entrypoint bash timelike-agent:local -c

lint: docker-check
	@docker image inspect timelike-agent:local >/dev/null 2>&1 || $(MAKE) build
	docker run --rm -v "$(CURDIR)":/mnt:ro -w /mnt $(SHELLCHECK_IMAGE) $(SHELLCHECK_FILES)
	$(PY_IN_IMAGE) 'set -e; P=/opt/timelike/python/bin/python3; \
	  uv tool run --python $$P ruff@$(RUFF_VERSION) check --no-cache tools tests scan bench scripts; \
	  uv tool run --python $$P ruff@$(RUFF_VERSION) format --no-cache --check tools tests scan bench scripts; \
	  uv tool run --python $$P mypy@$(MYPY_VERSION) --cache-dir /tmp/mypy'
	docker run --rm -u "$$(id -u):$$(id -g)" -v "$(CURDIR)/adele":/src:ro -w /src -e HOME=/tmp \
	  -e GOCACHE=/tmp/gocache -e GOMODCACHE=/tmp/gomod -e GOFLAGS=-mod=readonly -e GOTOOLCHAIN=local \
	  -e CGO_ENABLED=0 $(GO_IMAGE) bash -c 'set -e; go version; f=$$(gofmt -l .); test -z "$$f" || { echo "gofmt: $$f"; exit 1; }; \
	  go vet ./...'
	# staticcheck alone runs in GO_LINT_IMAGE (pins.env says why, and when it goes).
	docker run --rm -u "$$(id -u):$$(id -g)" -v "$(CURDIR)/adele":/src:ro -w /src -e HOME=/tmp \
	  -e GOCACHE=/tmp/gocache -e GOMODCACHE=/tmp/gomod -e GOFLAGS=-mod=readonly -e GOTOOLCHAIN=local \
	  -e CGO_ENABLED=0 $(GO_LINT_IMAGE) bash -c 'set -e; echo "staticcheck on $$(go version)"; \
	  go run honnef.co/go/tools/cmd/staticcheck@$(STATICCHECK_VERSION) ./...'

# Fallback when no daemon is reachable: whatever of ruff/mypy/shellcheck the host has. Advisory.
lint-host:
	@command -v ruff >/dev/null && ruff check tools tests scan bench scripts && ruff format --check tools tests scan bench scripts || echo "lint-host: ruff not available"
	@$(PYTHON) -m mypy --version >/dev/null 2>&1 && $(PYTHON) -m mypy || echo "lint-host: mypy not available"
	@command -v shellcheck >/dev/null && shellcheck $(SHELLCHECK_FILES) || echo "lint-host: shellcheck not available"
	@command -v go >/dev/null && (cd adele && test -z "$$(gofmt -l .)" && go vet ./...) || echo "lint-host: go not available (or gofmt/vet failed)"

scan: docker-check
	scan/scan.sh

demo: up
	scripts/demo.sh

# Speedup bench (feature 002). Three images, all from the pinned base and stamped with the checkout's
# revision: the agent (make build), the vanilla baseline and the bench driver. The driver refuses any
# image whose revision label differs from GIT_SHA (research RB8), so a stale image is never measured.
#   make bench                              all catalog tasks
#   make bench TASKS=git-rebase-continue    one task (space-separated for several)
bench-images: build
	docker build -f bench/vanilla/Dockerfile --build-arg DEBIAN_IMAGE=$(DEBIAN_IMAGE) \
	  --build-arg UV_IMAGE=$(UV_IMAGE) --build-arg PYTHON_VERSION=$(PYTHON_VERSION) \
	  --build-arg NODE_VERSION=$(NODE_VERSION) --build-arg NODE_SHA256=$(NODE_SHA256) \
	  --build-arg NPM_VERSION=$(NPM_VERSION) --build-arg NPM_SHA512=$(NPM_SHA512) \
	  --build-arg GIT_SHA=$(GIT_SHA) -t timelike-vanilla:local .
	docker build -f bench/driver/Dockerfile --build-arg DEBIAN_IMAGE=$(DEBIAN_IMAGE) \
	  --build-arg UV_IMAGE=$(UV_IMAGE) --build-arg PYTHON_VERSION=$(PYTHON_VERSION) \
	  --build-arg DOCKER_CLI_IMAGE=$(DOCKER_CLI_IMAGE) --build-arg GIT_SHA=$(GIT_SHA) \
	  -t timelike-bench-driver:local .

bench: bench-images
	bench/run.sh $(foreach t,$(TASKS),--task $(t))
