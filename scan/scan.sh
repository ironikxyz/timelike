#!/usr/bin/env bash
# Supply-chain scan gate (constitution H9; quality-standards "Supply-chain scan"). Run by `make scan`,
# which has already checked that a Docker daemon answers. Every scanner runs from its pinned image in
# pins.env; nothing is installed on the host.
#
#   1. SBOM        Syft over `docker save` of each image
#   2. grype       Grype over that SBOM, JSON only
#   3. pip-audit   over timelike's interpreter's installed distributions, via uv inside the image. An
#                  image without timelike's interpreter (vanilla; Adele's scratch stage) records none.
#  3b. pip-audit-agent  over the AGENT interpreter's (/opt/agent/python; discovery revision 14) installed
#                  distributions, in every image that carries it (agent, vanilla), as a result line of
#                  its own. The scanned image's agent interpreter lists them as exact pins; the agent
#                  image's uv runs pip-audit over that list (-r, --no-deps --disable-pip: nothing is
#                  resolved or installed), because vanilla has no uv. An image without it records none.
#                  Node with npm's bundled packages is in the agent and vanilla SBOMs, so Grype covers
#                  it (and the agent Python again) under the same baseline rule
#  3c. release-check  for each BUNDLED-CLASS entry in the image's baseline (a library bundled inside a
#                  component, e.g. npm's own node_modules; discovery revision 15): does any stable release
#                  of the component inside the stack's constraint ship the fix? evaluate.py releases reads
#                  the registry's released tarballs, from the agent image, WITH network. The verdict lets
#                  such a finding through only on its "no release" answer; a release that ships the fix,
#                  or a check that could not run, blocks (fails closed). No bundled entries: none
#   4. govulncheck Adele only: govulncheck GOVULNCHECK_VERSION over adele/ (source, symbol level), run
#                  from GO_IMAGE. Other images record none (not a Go image)
#   5. gitleaks    over the repository's git history (once; its report is shared by every image)
#   then, once, not per image: the publish deny-list over the TRACKED TREE at HEAD (scan/denylist.py;
#   maintenance send, publish redaction, 2026-10-02). It reads its list from OUTSIDE the repository
#   (TIMELIKE_PUBLISH_DENYLIST, default ../bridge/publish-denylist.txt), so the rule cannot publish what
#   it hides, and it reports entry ids and file:line, never a matched string. A match fails the scan.
#   With no list (a public clone has no ../bridge/) it reports `unknown — no deny-list available` and
#   does not fail: nothing was checked, so it is never a pass. It scans the tree, not history: history
#   keeps these strings until the publishing step starts a new root, and gitleaks already reads history
#
# Four images (feature 002, FR-16: every image the bench adds goes through the same gate; feature 004,
# research R5: Adele's too):
#   timelike-agent:local          → scan/out/                       required (unchanged since 001)
#   timelike-adele:local          → scan/out/timelike-adele/        required. FROM scratch: no interpreter,
#                                    so pip-audit records none; its base digest is GO_IMAGE's (below)
#   timelike-vanilla:local        → scan/out/timelike-vanilla/      (bench baseline; no timelike interpreter,
#                                    so pip-audit records none; pip-audit-agent audits its agent
#                                    interpreter, and its runtimes are in its SBOM)
#   timelike-bench-driver:local   → scan/out/timelike-bench-driver/ (holds the docker CLI, a Go binary:
#                                    grype may report fixable Go-stdlib Highs that block until
#                                    DOCKER_CLI_IMAGE is bumped, research RB10)
# Each image is judged against its own reviewed baseline, scan/baseline/<image>.json. An image with no
# baseline accepts nothing: its proposed baseline is written for a person to review, never adopted
# from another image's review. The two required images (make build) must exist, or the scan fails
# before anything runs. The bench images are scanned only when they exist (make bench-images); an
# absent one is reported, and does not fail the scan. Exit 1 if any image fails.
#
# No scanner's exit code or message decides anything (H3). Each step records ran | none | error in
# scan/out/steps.tsv, and scan/evaluate.py (run with the image's own interpreter, `python3 -I`) reads
# the JSON each step wrote and applies the H9 rule of discovery revision 5: an unfixable High or
# Critical passes only through the reviewed baseline scan/baseline/<image>.json, recorded for the
# image's pinned base digest (base_digest_of, below). Its first stdout line is the verdict, and one line
# summarises what the baseline accepts. scan/out/verdict.json summarises the verdict, and
# scan/out/baseline.proposed.json is the baseline this scan would need, for a person to review.
# Exit 0 on PASS, 1 on anything else, including a step that could not run. Progress and scanner
# chatter go to stderr.
#
# Bind mounts name paths on the daemon's host: with a remote DOCKER_HOST, the checkout must exist at
# the same path there.
#
# Network: grype fetches its vulnerability database, pip-audit queries PyPI's advisory service, and
# govulncheck downloads itself (go run …@GOVULNCHECK_VERSION, into a throwaway module cache) and reads
# the Go vulnerability database (vuln.go.dev). Syft, gitleaks and evaluate.py run with --network none.
set -euo pipefail

cd "$(dirname "$0")/.."
root=$PWD
# shellcheck source=pins.env
. "$root/pins.env"

agent=timelike-agent:local
adele=timelike-adele:local
image=$agent
top=scan/out
out=$top
py=/opt/timelike/python/bin/python3
agent_py=/opt/agent/python/bin/python3
as_me=(--user "$(id -u):$(id -g)")

die() {
  printf 'scan: %s [supply-chain] — FAIL\n' "$image"
  printf 'error: %s\n' "$1" >&2
  exit 1
}
record() { printf '%s\t%s\t%s\n' "$1" "$2" "$(printf '%s' "$3" | tr '\t\n' '  ')" >>"$out/steps.tsv"; }
reason() { grep -v '^[[:space:]]*$' "$1" 2>/dev/null | tail -n 1 | cut -c1-240 || true; }
progress() { printf 'scan: %s\n' "$1" >&2; }

# base_digest_of IMAGE — the digest of the pinned image IMAGE is built FROM, which its baseline is
# recorded for. The one place this mapping lives (research R5). Adele's final stage is FROM scratch,
# which has no base layer; its only base is the Go builder, so Debian's digest would be false for it.
base_digest_of() {
  case $1 in
    "$adele") printf '%s\n' "${GO_IMAGE##*@}" ;;
    *) printf '%s\n' "${DEBIAN_IMAGE##*@}" ;; # agent, vanilla, bench-driver: built FROM DEBIAN_IMAGE
  esac
}

# Required images: a missing one fails the scan before anything runs (research R5: Adele is required,
# like the agent; a skip would pass a gate that never looked at it).
for image in "$agent" "$adele"; do
  docker image inspect "$image" >/dev/null 2>&1 \
    || die "image $image not found (code 1) — build it with make build first"
done
image=$agent

rm -rf "$top"
mkdir -p "$top"

# scan_image IMAGE OUT — steps 1-4 (3b included) for one image, into OUT/steps.tsv (step 5, gitleaks,
# is appended by the caller).
scan_image() {
image=$1
out=$2
mkdir -p "$out"
: >"$out/steps.tsv"
image_id=$(docker image inspect --format '{{.Id}}' "$image")

# --- 1. SBOM. `docker save` + docker-archive instead of mounting the Docker socket into Syft: the
# socket is root on the host, and the archive works the same under a remote DOCKER_HOST.
progress "[1/5] SBOM of $image ($image_id) with ${SYFT_IMAGE%%@*}"
sbom_ok=
if docker save --output "$out/agent-image.tar" "$image" 2>"$out/sbom.err" \
  && chmod a+r "$out/agent-image.tar" \
  && docker run --rm --network none -e SYFT_CHECK_FOR_APP_UPDATE=false \
    -v "$root/$out:/in:ro" "$SYFT_IMAGE" \
    docker-archive:/in/agent-image.tar -o syft-json >"$out/sbom.syft.json" 2>>"$out/sbom.err"; then
  sbom_ok=1
  record sbom ran "syft ${SYFT_IMAGE%%@*}"
else
  record sbom error "could not produce an SBOM (exit $?): $(reason "$out/sbom.err")"
fi
rm -f "$out/agent-image.tar"

# --- 2. Grype over the SBOM. No --fail-on and no --only-fixed: grype lists every match and
# evaluate.py decides (fixable High/Critical blocks; unfixable needs the baseline). A non-zero exit
# here therefore means grype itself failed, e.g. no network for its vulnerability database.
progress "[2/5] vulnerabilities with ${GRYPE_IMAGE%%@*}"
if [ -z "$sbom_ok" ]; then
  record grype error "not run: no SBOM (step 1 failed)"
elif docker run --rm -e GRYPE_CHECK_FOR_APP_UPDATE=false -v "$root/$out:/in:ro" "$GRYPE_IMAGE" \
  sbom:/in/sbom.syft.json -o json >"$out/grype.json" 2>"$out/grype.err"; then
  record grype ran "grype ${GRYPE_IMAGE%%@*}"
else
  record grype error "grype failed (exit $?): $(reason "$out/grype.err")"
fi

# evaluate.py under an interpreter, no network, as the invoking user so it can write scan/out.
# `-I`: no PYTHONPATH, user site or script directory (research R6). The listing of distributions runs
# in the scanned image's own interpreter; an image without one (the vanilla baseline) has nothing
# pip-audit could audit, and says so.
py_opts=(--rm --network none "${as_me[@]}" --entrypoint "$py" -v "$root/scan:/scan:ro" -v "$root/$out:/out")

# --- 3. pip-audit. First ask the image's interpreter what is installed. If nothing is, say so and
# pass: an audit of nothing is not a scan. Otherwise audit exactly that site-packages directory.
# pip-audit exits 1 when it finds something, so the JSON decides, not the code.
# The probe runs the interpreter itself as the entrypoint, not `/bin/sh -c "test -x"`: a scratch image
# (Adele) has no shell, so that probe failed for a reason it did not name. `docker run` exits 127 (or
# 126) when the entrypoint cannot be found or run, which is this image having no interpreter; any other
# failure (125: the daemon refused) is an error, never "nothing to audit" (H3).
progress "[3/5] pip-audit $PIP_AUDIT_VERSION over the image interpreter's distributions"
probe=0
docker run --rm --network none --entrypoint "$py" "$image" -I -c '' >/dev/null 2>"$out/pip-audit.err" \
  || probe=$?
if [ "$probe" -eq 126 ] || [ "$probe" -eq 127 ]; then
  record pip-audit none "no interpreter in image: $image has no $py, so pip-audit had nothing to audit"
elif [ "$probe" -ne 0 ]; then
  record pip-audit error "could not probe $image for $py (docker exit $probe): $(reason "$out/pip-audit.err")"
elif listing=$(docker run "${py_opts[@]}" "$image" -I /scan/evaluate.py dists --out /out/dists.json \
  2>"$out/pip-audit.err") \
  && read -r count purelib <<<"$listing" && [[ $count =~ ^[0-9]+$ && -n $purelib ]]; then
  if [ "$count" -eq 0 ]; then
    record pip-audit none "no third-party packages — pip-audit had nothing to audit"
  elif docker run --rm "${as_me[@]}" -e HOME=/tmp -e UV_CACHE_DIR=/tmp/uv-cache \
    -e UV_TOOL_DIR=/tmp/uv-tools --entrypoint /bin/uv -v "$root/$out:/out" "$image" \
    tool run --python "$py" "pip-audit==$PIP_AUDIT_VERSION" --path "$purelib" \
    --format json --output /out/pip-audit.json --progress-spinner off 2>>"$out/pip-audit.err"; then
    record pip-audit ran "$count distributions in $purelib"
  else
    rc=$?
    if [ -s "$out/pip-audit.json" ]; then
      record pip-audit ran "$count distributions in $purelib (pip-audit exit $rc; its JSON decides)"
    else
      record pip-audit error "pip-audit wrote no report (exit $rc): $(reason "$out/pip-audit.err")"
    fi
  fi
else
  record pip-audit error "could not list the image's distributions: $(reason "$out/pip-audit.err")"
fi

# --- 3b. pip-audit over the agent interpreter (lane 007s1-a, item 4: quality-standards says the scan
# covers the runtimes). The same probe as step 3, for $agent_py. The listing runs in the scanned image's
# own agent interpreter, so it names what that image ships; the audit runs from the agent image, which
# holds uv and timelike's interpreter, over that list alone. pip-audit exits 1 when it finds something,
# so the JSON decides, not the code.
progress "[3/5] pip-audit $PIP_AUDIT_VERSION over the agent interpreter's distributions"
aerr=$out/pip-audit-agent.err
probe=0
docker run --rm --network none --entrypoint "$agent_py" "$image" -I -c '' >/dev/null 2>"$aerr" || probe=$?
if [ "$probe" -eq 126 ] || [ "$probe" -eq 127 ]; then
  record pip-audit-agent none \
    "no agent interpreter in image: $image has no $agent_py, so pip-audit had nothing to audit"
elif [ "$probe" -ne 0 ]; then
  record pip-audit-agent error "could not probe $image for $agent_py (docker exit $probe): $(reason "$aerr")"
elif listing=$(docker run --rm --network none "${as_me[@]}" --entrypoint "$agent_py" \
  -v "$root/scan:/scan:ro" -v "$root/$out:/out" "$image" -I /scan/evaluate.py dists \
  --out /out/dists-agent.json --requirements /out/agent-requirements.txt 2>"$aerr") \
  && read -r count purelib <<<"$listing" && [[ $count =~ ^[0-9]+$ && -n $purelib ]]; then
  if [ "$count" -eq 0 ]; then
    record pip-audit-agent none "no distributions in the agent interpreter — pip-audit had nothing to audit"
  elif docker run --rm "${as_me[@]}" -e HOME=/tmp -e UV_CACHE_DIR=/tmp/uv-cache \
    -e UV_TOOL_DIR=/tmp/uv-tools --entrypoint /bin/uv -v "$root/$out:/out" "$agent" \
    tool run --python "$py" "pip-audit==$PIP_AUDIT_VERSION" -r /out/agent-requirements.txt --no-deps \
    --disable-pip --format json --output /out/pip-audit-agent.json --progress-spinner off 2>>"$aerr"; then
    record pip-audit-agent ran "$count distributions in $purelib (agent interpreter)"
  else
    rc=$?
    if [ -s "$out/pip-audit-agent.json" ]; then
      record pip-audit-agent ran \
        "$count distributions in $purelib (agent interpreter; pip-audit exit $rc; its JSON decides)"
    else
      record pip-audit-agent error "pip-audit wrote no report (exit $rc): $(reason "$aerr")"
    fi
  fi
else
  record pip-audit-agent error "could not list the agent interpreter's distributions: $(reason "$aerr")"
fi

# --- 3c. The release check (discovery revision 15). It runs on the agent image's timelike interpreter,
# like the verdict, because only that image is sure to have one; the scanned image's baseline is read from
# /scan. It needs the registry (network on), and it records what it checked: its summary is the detail.
# A failure to run is an error, never "nothing to check" (H3): the verdict then blocks every bundled entry.
progress "[3/5] release check for the baseline's bundled-class entries"
rerr=$out/release-check.err
baseline_file=scan/baseline/${image%%:*}.json
if [ ! -f "$baseline_file" ]; then
  record release-check none "no baseline ($baseline_file), so no bundled-class entries to check"
elif listing=$(docker run --rm "${as_me[@]}" --entrypoint "$py" -v "$root/scan:/scan:ro" -v "$root/$out:/out" \
  "$agent" -I /scan/evaluate.py releases --baseline "/$baseline_file" --node-version "$NODE_VERSION" \
  --out /out/release-check.json 2>"$rerr") \
  && read -r count summary <<<"$listing" && [[ $count =~ ^[0-9]+$ ]]; then
  if [ "$count" -eq 0 ]; then
    record release-check none "$summary"
  else
    record release-check ran "$count $summary"
  fi
else
  record release-check error "the release check could not run: $(reason "$rerr")"
fi

# --- 4. govulncheck, Adele only (research R5): over Adele's source, at symbol level, so evaluate.py can
# tell a vulnerable function Adele calls (gated as High) from one it only imports (never blocks).
# Run from GO_IMAGE, the builder Adele's binaries come from, with adele/ mounted read-only:
# GOFLAGS=-mod=readonly so go.mod and go.sum are never rewritten, GOTOOLCHAIN=local so the scan uses
# the pinned Go and never downloads another, caches in the container's /tmp. Needs network (above).
# In JSON mode govulncheck exits 0 whether or not it finds anything, so a non-zero exit means it
# failed; the JSON decides, not the code.
progress "[4/5] reachable Go vulnerabilities with govulncheck $GOVULNCHECK_VERSION"
if [ "$image" != "$adele" ]; then
  record govulncheck none "not a Go image: govulncheck runs over Adele's source only"
elif docker run --rm "${as_me[@]}" -e HOME=/tmp -e GOPATH=/tmp/go -e GOCACHE=/tmp/go-cache \
  -e GOMODCACHE=/tmp/go-mod -e GOTOOLCHAIN=local -e GOFLAGS=-mod=readonly \
  -v "$root/adele:/src:ro" -w /src --entrypoint go "$GO_IMAGE" \
  run "golang.org/x/vuln/cmd/govulncheck@$GOVULNCHECK_VERSION" -format json ./... \
  >"$out/govulncheck.json" 2>"$out/govulncheck.err"; then
  if [ -s "$out/govulncheck.json" ]; then
    record govulncheck ran "govulncheck $GOVULNCHECK_VERSION over adele/ (${GO_IMAGE%%@*})"
  else
    record govulncheck error "govulncheck exited 0 but wrote no report"
  fi
else
  record govulncheck error "govulncheck failed (exit $?): $(reason "$out/govulncheck.err")"
fi

}

# --- 5. gitleaks over git history. v8.19 made `detect` a deprecated alias; `git` is the current
# subcommand for history (`dir` scans only the working tree, which misses a secret committed and
# later deleted). --exit-code 0 makes a leak exit 0 too, so a non-zero exit can only mean gitleaks
# failed; findings come from the JSON. --redact keeps the secrets themselves out of scan/out.
# --config is the rule set run's output redaction reads too (feature 003 slice 1, FR-33): gitleaks'
# defaults, extended by 18 of them tagged with their redaction type, so the scan's rules are unchanged.
# Run as the invoking user, who owns the checkout, so git's safe.directory check passes.
# gitleaks_step — once, into scan/out; its record is appended to every image's steps.tsv.
gitleaks_step() {
out=$top
progress "[5/5] committed secrets with ${GITLEAKS_IMAGE%%@*}"
if [ ! -d .git ]; then
  record gitleaks error "not a plain git checkout (.git is not a directory), so history cannot be mounted"
elif docker run --rm --network none "${as_me[@]}" -e HOME=/tmp \
  -v "$root:/repo:ro" -v "$root/$out:/out" "$GITLEAKS_IMAGE" \
  git /repo --no-banner --redact --exit-code 0 --config /repo/image/rootfs/etc/timelike/redaction.toml \
  --report-format json --report-path /out/gitleaks.json >"$out/gitleaks.err" 2>&1; then
  if [ -s "$out/gitleaks.json" ]; then
    record gitleaks ran "gitleaks ${GITLEAKS_IMAGE%%@*}"
  else
    record gitleaks error "gitleaks exited 0 but wrote no report"
  fi
else
  record gitleaks error "gitleaks failed (exit $?): $(reason "$out/gitleaks.err")"
fi
}

# verdict IMAGE OUT — evaluate.py prints everything at once, so a crash never leaves half a verdict.
# It always runs on the AGENT image's timelike interpreter: the vanilla baseline has none (its agent
# runtimes are not timelike's). The baseline is read
# from /scan (the scan/ directory, mounted read-only); an absent file accepts nothing.
verdict() {
  local rc=0 baseline=scan/baseline/${1%%:*}.json
  image=$1
  out=$2
  image_id=$(docker image inspect --format '{{.Id}}' "$image")
  docker run --rm --network none "${as_me[@]}" --entrypoint "$py" -v "$root/scan:/scan:ro" \
    -v "$root/$out:/out" "$agent" \
    -I /scan/evaluate.py report --out /out --baseline "/$baseline" --baseline-label "$baseline" \
    --base-digest "$(base_digest_of "$image")" --image "$image" --image-id "$image_id" \
    || rc=$?
  [ "$rc" -le 1 ] || die "the evaluator failed (exit $rc), so no verdict could be reached"
  return "$rc"
}

gitleaks_step
gitleaks_line=$(grep "^gitleaks$(printf '\t')" "$top/steps.tsv" || true)
: >"$top/steps.tsv"

final=0
for img in "$agent" "$adele" timelike-vanilla:local timelike-bench-driver:local; do
  dir=$top
  [ "$img" = "$agent" ] || dir=$top/${img%%:*}
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    if [ "$img" = "$agent" ] || [ "$img" = "$adele" ]; then
      image=$img
      die "image $img not found (code 1) — build it with make build first"
    fi
    printf 'scan: %s [supply-chain] — not present (build it with make bench-images); not scanned\n' "$img"
    continue
  fi
  scan_image "$img" "$dir"
  printf '%s\n' "$gitleaks_line" >>"$dir/steps.tsv"
  if [ "$dir" != "$top" ] && [ -s "$top/gitleaks.json" ]; then cp "$top/gitleaks.json" "$dir/gitleaks.json"; fi
  verdict "$img" "$dir" || final=1
done

# --- the publish deny-list over the tracked tree at HEAD (see the header). `git archive HEAD` is the
# tree exactly as committed, whatever the working tree holds; `git ls-tree` gives the count it must
# match. The check runs on the agent image's interpreter and GNU grep, with no network, and the list is
# mounted read-only only when it exists.
denylist=${TIMELIKE_PUBLISH_DENYLIST:-../bridge/publish-denylist.txt}
dl_label=$denylist
dl_mount=()
dl_arg=/denylist-absent
if [ -f "$denylist" ]; then
  dl_mount=(-v "$(cd "$(dirname "$denylist")" && pwd)/$(basename "$denylist"):/denylist:ro")
  dl_arg=/denylist
fi
progress "publish deny-list over the tracked tree at HEAD ($dl_label)"
dl_rc=0
git archive HEAD | docker run --rm -i --network none "${as_me[@]}" --entrypoint "$py" \
  -v "$root/scan:/scan:ro" -v "$root/$top:/out" "${dl_mount[@]}" "$agent" \
  -I /scan/denylist.py --list "$dl_arg" --list-label "$dl_label" \
  --expect-files "$(git ls-tree -r HEAD --name-only | wc -l)" --out /out/denylist.json \
  || dl_rc=$?
# 0 pass or unknown, 1 a tracked line matches, 2 the check could not run: both of the last fail
[ "$dl_rc" -eq 0 ] || final=1
exit "$final"
