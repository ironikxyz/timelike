#!/usr/bin/env bash
# MANUAL DEMO for SC-7 (→ D1). A person must WATCH this run: it asserts nothing, the watcher judges.
#
# `make demo` runs this after `make up`. Inside the running timelike-agent container, as the harness
# would (bash -c), it runs
#   git commit            (no message, on a staged change)
#   git rebase --continue (on a conflict already resolved and staged)
#   git log               (more than one screen of history)
# each in three terminal modes — no terminal (the harness's own invocation), docker exec -t, and a pty
# made by util-linux script inside the container — and prints each command's exit code and elapsed
# seconds. Expected: every command returns within seconds; no editor, pager or prompt appears;
# git commit exits 1 with "Aborting commit due to empty commit message"; rebase --continue exits 0.
#
# The watcher records what they saw in the cycle report (SC-7 `observed by <who>`); if nobody watched,
# SC-7 stays `unconfirmed`, whatever this script printed.
set -uo pipefail

echo "MANUAL DEMO (SC-7 → D1): a person must watch this run. Nothing is asserted; you are the check."
echo

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
container="${AGENT_CONTAINER:-timelike-agent}"
limit="${DEMO_TIMEOUT:-60}"

if ! docker inspect -f '{{.State.Running}}' "${container}" 2>/dev/null | grep -qx true; then
  echo "error: container ${container} is not running (code 1) — run 'make demo' (it builds and starts it) or 'make up'" >&2
  exit 1
fi

have_timeout=0
if command -v timeout >/dev/null 2>&1; then
  have_timeout=1
else
  echo "note: no 'timeout' on this host; a hang would not be cut off at ${limit}s — interrupt it yourself"
fi

now_ms() {
  if [[ -n "${EPOCHREALTIME:-}" ]]; then
    local t="${EPOCHREALTIME/[.,]/}"
    echo $((10#${t} / 1000))
  else
    echo $(($(date +%s) * 1000))
  fi
}

# Copy the SC-1 repository fixture in as the agent user (the same fixture the e2e tests use).
docker exec -i "${container}" sh -c 'cat > /tmp/demo-repo.sh && chmod 0755 /tmp/demo-repo.sh' \
  <"${repo}/tests/e2e/fixtures/sc1-repo.sh" || {
  echo "error: could not copy the repository fixture into ${container} (code 1)" >&2
  exit 1
}

declare -a SUMMARY=()

# demo MODE STATE COMMAND
demo() {
  local mode="$1" state="$2" cmd="$3" dir rc start end ms
  dir="$(docker exec "${container}" mktemp -d /tmp/demo.XXXXXX)" || return 1
  if ! docker exec "${container}" sh /tmp/demo-repo.sh "${dir}/repo" "${state}" >/dev/null; then
    echo "error: preparing the ${state} repository failed" >&2
    return 1
  fi
  local full="cd '${dir}/repo' && ${cmd}"
  local -a run
  # shellcheck disable=SC2016 # $TL_CMD expands inside the container
  case "${mode}" in
    no-tty) run=(docker exec "${container}" bash -c "${full}") ;;
    tty) run=(docker exec -t "${container}" bash -c "${full}") ;;
    pty) run=(docker exec -e "TL_CMD=${full}" "${container}" script -qec 'bash -c "$TL_CMD"' /dev/null) ;;
  esac
  if ((have_timeout)); then
    run=(timeout "${limit}" "${run[@]}")
  fi

  echo "──────────────────────────────────────────────────────────────────────────"
  echo "\$ ${cmd}      [mode: ${mode}; via bash -c in ${container}]"
  echo "──────────────────────────────────────────────────────────────────────────"
  start="$(now_ms)"
  "${run[@]}" </dev/null
  rc=$?
  end="$(now_ms)"
  ms=$((end - start))
  local secs
  secs="$(printf '%d.%03d' $((ms / 1000)) $((ms % 1000)))"
  echo
  echo "→ rc=${rc}  elapsed=${secs}s"
  local left
  left="$(docker exec "${container}" pgrep -a -x 'less|more|most|pager|vi|vim|vim\.basic|vim\.tiny|nano|editor|sensible-editor' || true)"
  if [[ -n "${left}" ]]; then
    echo "→ pager/editor processes still running in the container:"
    echo "${left}"
  else
    echo "→ no pager or editor process left in the container"
  fi
  echo
  SUMMARY+=("$(printf '%-26s %-7s rc=%-4s %8ss' "${cmd}" "${mode}" "${rc}" "${secs}")")
  docker exec "${container}" rm -rf "${dir}" >/dev/null 2>&1 || true
}

for mode in no-tty tty pty; do
  demo "${mode}" commit "git commit"
  demo "${mode}" rebase "git rebase --continue"
  demo "${mode}" log "git log"
done

docker exec "${container}" rm -f /tmp/demo-repo.sh >/dev/null 2>&1 || true

echo "══════════════════════════════════════════════════════════════════════════"
echo "Summary (as printed above; the watcher decides whether each returned within seconds):"
printf '  %s\n' "${SUMMARY[@]}"
echo "Expected: git commit rc=1, git rebase --continue rc=0, git log rc=0; each within seconds;"
echo "no editor, pager or prompt seen. Record what you watched in the cycle report (SC-7)."
