# Adele (feature 004, slice 0) and the test-only stand-in. Build context: adele/ (compose.yaml).
#
# Two final stages from one builder (research R2): `adele` ships; `standin` exists for tests and the
# D8 demo only (compose profile `standin`) and is never in Adele's image. Both are FROM scratch with a
# static binary: CGO_ENABLED=0, SQLite through modernc.org/sqlite (tech-stack; mattn/go-sqlite3 and cgo
# are prohibited). GO_IMAGE arrives from pins.env through the Makefile and compose.yaml, as every pin
# does. The revision stamp is refused when empty or not a git revision (H8, lore cross-stack P003).

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

# --- Adele: the authority. uid 10001 ("adele", the same uid 001's agent image reserves; spec D-6). ---
FROM scratch AS adele
ARG GIT_SHA
COPY --from=build /out/adeled /usr/local/bin/adeled
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
