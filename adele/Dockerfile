# Adele (feature 004, slice 0) and the test-only stand-in. Build context: adele/ (compose.yaml).
#
# Two final stages from one builder (research R2): `adele` ships; `standin` exists for tests and the
# D8 demo only (compose profile `standin`) and is never in Adele's image. Both are FROM scratch with a
# static binary: CGO_ENABLED=0, SQLite through modernc.org/sqlite (tech-stack; mattn/go-sqlite3 and cgo
# are prohibited). GO_IMAGE arrives from pins.env through the Makefile and compose.yaml, as every pin
# does. The revision stamp is refused when empty or not a git revision (H8, lore cross-stack P003).
#
# Feature 13 slice 0 (014 research R1): Adele's image also carries the Compose CLI, run standalone as
# docker-compose. Since Cycle 2 (lane 13s0a, item E) it is built here from source, at COMPOSE_VERSION with
# golang.org/x/net raised to COMPOSE_XNET_VERSION, by GO_IMAGE's Go: the release binary in the docker CLI
# image was go1.26.8 with x/net v0.58.0, and no newer release existed. The module comes from the Go proxy,
# checked against COMPOSE_SUM and the checksum database. The binary is refused unless its Go build info says
# CGO_ENABLED=0 and the pinned x/net: a dynamically linked binary cannot run FROM scratch, and choosing a base
# instead is the operator's decision, not this build's (Item 27 Q1).

ARG GO_IMAGE

FROM ${GO_IMAGE} AS build
SHELL ["/bin/bash", "-o", "errexit", "-o", "nounset", "-o", "pipefail", "-c"]
ARG GIT_SHA
RUN if [ -z "${GIT_SHA:-}" ]; then \
      echo "GIT_SHA build arg is empty — refusing to build an unstamped image (H8)" >&2; exit 1; fi \
 && if ! [[ "${GIT_SHA}" =~ ^[0-9a-f]{7,64}$ ]]; then \
      echo "GIT_SHA build arg '${GIT_SHA}' is not a git revision — refusing to stamp it (H8)" >&2; exit 1; fi
ENV CGO_ENABLED=0 GOTOOLCHAIN=local GOFLAGS=-mod=readonly
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download && go mod verify
COPY cmd/ cmd/
COPY internal/ internal/
RUN go build -trimpath -ldflags "-s -w -X main.revision=${GIT_SHA}" -o /out/adeled ./cmd/adeled \
 && go build -trimpath -ldflags "-s -w" -o /out/adele-standin ./cmd/adele-standin \
 && test "$(/out/adeled version)" = "${GIT_SHA}" \
 && install -d -o 10001 -g 10001 -m 0700 /out/state/adele /out/state/standin
ARG COMPOSE_VERSION
ARG COMPOSE_SUM
ARG COMPOSE_XNET_VERSION
RUN if [ -z "${COMPOSE_VERSION:-}" ] || [ -z "${COMPOSE_SUM:-}" ] || [ -z "${COMPOSE_XNET_VERSION:-}" ]; then \
      echo "COMPOSE_VERSION, COMPOSE_SUM and COMPOSE_XNET_VERSION must come from pins.env" >&2; exit 1; fi \
 && got="$(go mod download -json "github.com/docker/compose/v5@${COMPOSE_VERSION}" | sed -n 's/^[[:space:]]*"Sum": "\(.*\)",$/\1/p')" \
 && if [ "${got}" != "${COMPOSE_SUM}" ]; then \
      echo "compose ${COMPOSE_VERSION} has sum '${got}', not the pinned ${COMPOSE_SUM}" >&2; exit 1; fi \
 && mkdir /compose && cp -r "$(go env GOMODCACHE)/github.com/docker/compose/v5@${COMPOSE_VERSION}/." /compose \
 && chmod -R u+w /compose
WORKDIR /compose
RUN go get "golang.org/x/net@${COMPOSE_XNET_VERSION}" && go mod verify \
 && go build -trimpath -ldflags "-s -w -X github.com/docker/compose/v5/internal.Version=${COMPOSE_VERSION}" \
      -o /out/docker-compose ./cmd \
 && go version -m /out/docker-compose > /out/compose-buildinfo.txt \
 && if ! grep -qE '^[[:space:]]+build[[:space:]]+CGO_ENABLED=0$' /out/compose-buildinfo.txt; then \
      echo "docker-compose is not built with CGO_ENABLED=0, so it cannot run FROM scratch." >&2; \
      echo "Raise it with the mentor; do not choose a base here (014 research R1, Item 27 Q1)." >&2; exit 1; fi \
 && if ! grep -qE "^[[:space:]]+dep[[:space:]]+golang.org/x/net[[:space:]]+${COMPOSE_XNET_VERSION}[[:space:]]" /out/compose-buildinfo.txt; then \
      echo "docker-compose does not carry golang.org/x/net ${COMPOSE_XNET_VERSION}" >&2; exit 1; fi \
 && test "$(/out/docker-compose version --short)" = "${COMPOSE_VERSION#v}"

# --- Adele: the authority. uid 10001 ("adele", the same uid 001's agent image reserves; spec D-6). ---
FROM scratch AS adele
ARG GIT_SHA
COPY --from=build /out/adeled /usr/local/bin/adeled
COPY --from=build /out/docker-compose /usr/local/bin/docker-compose
COPY --from=build --chown=10001:10001 /out/state/adele /var/lib/adele
USER 10001:10001
EXPOSE 8480
LABEL org.opencontainers.image.revision=$GIT_SHA \
      org.opencontainers.image.title="timelike-adele"
ENTRYPOINT ["/usr/local/bin/adeled"]
CMD ["serve"]

# --- The stand-in: NOT a provider. Test and demo only (spec FR-19; "What the stand-in proves"). -----
FROM scratch AS standin
ARG GIT_SHA
COPY --from=build /out/adele-standin /usr/local/bin/adele-standin
COPY --from=build --chown=10001:10001 /out/state/standin /var/lib/standin
USER 10001:10001
EXPOSE 8481
LABEL org.opencontainers.image.revision=$GIT_SHA \
      org.opencontainers.image.title="timelike-adele-standin (test stand-in, not a provider)"
ENTRYPOINT ["/usr/local/bin/adele-standin"]
CMD ["serve"]
