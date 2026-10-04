#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # setup_file exports what the @tests read; bats runs each @test in its own subshell by design
# Feature 007 (prompt 04, slice 0), SC-1 (tasks.md T003; spec FR-5 to FR-8, D-1, D-2):
#   SC-1 "On container start, a timelike announcement of at most 60 lines is present in each supported
#        harness's user-level context location and in the workspace's agent context file when none
#        exists, without overwriting an existing one"
#
# "On container start" is made real: setup_file starts THROWAWAY containers from the verified image
# (helpers.bash start_throwaway; the image the running agent container was created from, which
# stamp_check verified), so the image's ENTRYPOINT runs exactly as it does under compose. Nothing here
# runs `timelike announce --install` itself. Every check waits until the container's command (`sleep
# infinity`) is the child of PID 1 (docker-init), i.e. until the entrypoint has exec'd it, so "after
# start" is a fact read from the process table, not a sleep.
#
#   fresh     start_throwaway as is. The three user-level files (contract § Placement):
#             $HOME/.claude/CLAUDE.md, ${CODEX_HOME:-$HOME/.codex}/AGENTS.md,
#             $HOME/.config/opencode/AGENTS.md must each exist, be at most 60 lines and be byte-identical
#             (sha256) to /etc/timelike/announcement.md; `timelike announce --status --json` must report
#             each `current`, at the same path.
#   prepared  the same image and privilege boundary, but the container's own first process writes a
#             non-timelike ~/.claude/CLAUDE.md and creates a git repository ~/work, cd's into it and
#             only then execs the image's configured ENTRYPOINT (read from the image, not assumed)
#             with `sleep infinity`. That file must be left byte for byte, and reported `not placed`
#             with a reason; the other two are placed. start_throwaway cannot do this (it appends
#             `sleep infinity` after the image, which an --entrypoint /bin/sh would run as a script),
#             so this file runs its own `docker run` with start_throwaway's label, caps and init.
#
# THE WORKSPACE PART IS NOT BUILT (spec D-1, FR-7; FOR-MENTOR Item 19). The criterion says "and in the
# workspace's agent context file when none exists"; the send's seam says never write into a project.
# The spec follows the seam, so the workspace tests below assert the OPPOSITE of that clause: no
# CLAUDE.md or AGENTS.md is created in the workspace the entrypoint ran in (the image's WORKDIR in
# `fresh`; a git repository with neither file in `prepared`, which must also stay `git status` clean).
# Those tests are named "workspace part NOT built (D-1)" so the narrowing shows in the TAP stream, not
# only in this comment. If plan amends the criterion or the mentor overrules the seam, they change.
#
# Timing (spec Measurable outcomes: placement delays the start by at most 1 s). FLAGGED method: the
# placed files' mtimes (read in the container) against the container's State.StartedAt (read from the
# daemon); container and daemon share the host's clock. The last file must be written < 1000 ms after
# StartedAt. The first must not predate StartedAt by more than 1000 ms, and the image itself, started
# with its entrypoint overridden, must hold none of the three files: together these show the files were
# placed by this start, not baked into the image at build. StartedAt is taken when the daemon marks the
# container running, so it may trail the process's real start slightly; the bound is coarse (1 s) on
# purpose.
#
# Cells: bash -c and bash -lc in `notty` (the harness's own invocation). The reads are POSIX tools and
# the image's interpreter; the only timelike command under test is `timelike announce --status --json`.

load helpers

# The prepared container's own file: not timelike's (no marker line), one line, newline-terminated.
SC1_THEIRS='# operator context file, present before the container started (SC-1 test)'
SC1_HARNESSES=(claude-code codex opencode)

# The prepared container's first process (POSIX sh). $1 is the file content; the rest is the image's
# ENTRYPOINT, exec'd with the same command start_throwaway gives (`sleep infinity`).
SC1_PREPARE='set -e
mkdir -p "$HOME/.claude" "$HOME/work"
printf "%s\n" "$1" >"$HOME/.claude/CLAUDE.md"
shift
git -C "$HOME/work" init -q
cd "$HOME/work"
exec "$@" sleep infinity'

setup_file() {
  stamp_check
  remove_stale_throwaways
  SC1_FRESH="timelike-sc1-fresh-${RANDOM}${RANDOM}"
  SC1_PREPARED="timelike-sc1-prepared-${RANDOM}${RANDOM}"
  SC1_FRESH_ERROR=""
  SC1_PREPARED_ERROR=""
  SC1_IMAGE_ERROR=""
  SC1_FRESH_STARTED=""
  SC1_PREPARED_STARTED=""
  SC1_WORKDIR=""
  SC1_BAKED=""
  sc1_read_image || true
  sc1_start_fresh || true
  sc1_start_prepared || true
  export SC1_FRESH SC1_PREPARED SC1_FRESH_ERROR SC1_PREPARED_ERROR SC1_IMAGE_ERROR \
    SC1_FRESH_STARTED SC1_PREPARED_STARTED SC1_WORKDIR SC1_BAKED
}

teardown_file() {
  remove_throwaway "${SC1_FRESH:-}" "${SC1_PREPARED:-}"
}

# sc1_read_image — the image's WORKDIR, and which of the three files the image ITSELF holds, read by a
# throwaway whose entrypoint is overridden (so nothing is placed). Sets SC1_WORKDIR and SC1_BAKED.
sc1_read_image() {
  local image out
  image="$(agent_image)" || { SC1_IMAGE_ERROR="cannot read the image of ${AGENT_CONTAINER}"; return 1; }
  SC1_WORKDIR="$(timeout "$RUN_TIMEOUT" docker image inspect --format '{{.Config.WorkingDir}}' "$image" </dev/null 2>&1)" || {
    SC1_IMAGE_ERROR="cannot inspect ${image}: ${SC1_WORKDIR}"
    return 1
  }
  out="$(timeout "$RUN_TIMEOUT" docker run --rm --network none --label "${THROWAWAY_LABEL}=1" \
    --cap-drop ALL --security-opt no-new-privileges:true --entrypoint /bin/sh "$image" -c '
for f in "$HOME/.claude/CLAUDE.md" "${CODEX_HOME:-$HOME/.codex}/AGENTS.md" "$HOME/.config/opencode/AGENTS.md"; do
  if [ -e "$f" ]; then printf "%s " "$f"; fi
done
printf "read=done\n"' </dev/null 2>&1)"
  if [[ "$out" != *"read=done" ]]; then
    SC1_IMAGE_ERROR="cannot read the image's home with its entrypoint overridden: ${out}"
    return 1
  fi
  out="${out##*$'\n'}" # the last line only: docker may have printed a warning before it
  SC1_BAKED="${out%read=done}"
}

# sc1_wait_command NAME — wait (at most 10 s, in the container) until the container's command is
# running: `sleep` is a child of PID 1 (docker-init), so the entrypoint has finished and exec'd it.
# docker exec'd processes have parent 0, so this wait cannot see itself.
sc1_wait_command() {
  timeout "$RUN_TIMEOUT" docker exec "$1" sh -c '
n=0
until pgrep -x -P 1 sleep >/dev/null 2>&1; do
  n=$((n + 1))
  [ "$n" -lt 200 ] || exit 1
  sleep 0.05
done' </dev/null >/dev/null 2>&1
}

sc1_started_at() {
  timeout "$RUN_TIMEOUT" docker inspect --format '{{.State.StartedAt}}' "$1" </dev/null
}

sc1_start_fresh() {
  local err
  err="$(start_throwaway "$SC1_FRESH" 2>&1)" || {
    SC1_FRESH_ERROR="cannot start ${SC1_FRESH}: ${err}"
    return 1
  }
  sc1_wait_command "$SC1_FRESH" || {
    SC1_FRESH_ERROR="${SC1_FRESH}: the container's command (sleep infinity) was not running within 10 s of start — the entrypoint did not exec it (FR-8: placement never blocks the container)"
    return 1
  }
  SC1_FRESH_STARTED="$(sc1_started_at "$SC1_FRESH" 2>&1)" || {
    SC1_FRESH_ERROR="cannot read ${SC1_FRESH}'s StartedAt: ${SC1_FRESH_STARTED}"
    return 1
  }
}

sc1_start_prepared() {
  local image line err
  local -a entry=()
  image="$(agent_image)" || { SC1_PREPARED_ERROR="cannot read the image of ${AGENT_CONTAINER}"; return 1; }
  while IFS= read -r line; do
    [[ -n "$line" ]] && entry+=("$line")
  done < <(timeout "$RUN_TIMEOUT" docker image inspect --format '{{range .Config.Entrypoint}}{{println .}}{{end}}' "$image" </dev/null)
  if [[ ${#entry[@]} -eq 0 ]]; then
    SC1_PREPARED_ERROR="the image declares no ENTRYPOINT: nothing runs on container start (contract § The entrypoint)"
    return 1
  fi
  err="$(timeout "$RUN_TIMEOUT" docker run -d --rm --name "$SC1_PREPARED" --label "${THROWAWAY_LABEL}=1" \
    --cap-drop ALL --security-opt no-new-privileges:true --init \
    --entrypoint /bin/sh "$image" -c "$SC1_PREPARE" sc1-prepare "$SC1_THEIRS" "${entry[@]}" </dev/null 2>&1 >/dev/null)" || {
    SC1_PREPARED_ERROR="cannot start ${SC1_PREPARED}: ${err}"
    return 1
  }
  sc1_wait_command "$SC1_PREPARED" || {
    SC1_PREPARED_ERROR="${SC1_PREPARED}: the container's command (sleep infinity) was not running within 10 s of start — the preparation or the entrypoint (${entry[*]}) did not exec it"
    return 1
  }
  SC1_PREPARED_STARTED="$(sc1_started_at "$SC1_PREPARED" 2>&1)" || {
    SC1_PREPARED_ERROR="cannot read ${SC1_PREPARED}'s StartedAt: ${SC1_PREPARED_STARTED}"
    return 1
  }
}

# sc1_ready fresh|prepared — fail with the setup's reason, if any.
sc1_ready() {
  if [[ -n "${SC1_IMAGE_ERROR:-}" ]]; then
    echo "SC-1 precondition: ${SC1_IMAGE_ERROR}" >&2
    return 1
  fi
  local err
  if [[ "$1" == fresh ]]; then err="${SC1_FRESH_ERROR:-}"; else err="${SC1_PREPARED_ERROR:-}"; fi
  if [[ -n "$err" ]]; then
    echo "SC-1 precondition: ${err}" >&2
    return 1
  fi
}

# READ_PLACEMENTS — run under the style under test, in a throwaway. Paths are computed in the
# container from its own HOME and CODEX_HOME (contract § Placement). Input: SC1_STARTED_AT (the
# daemon's StartedAt) and SC1_THEIRS (the prepared file's content), passed with -e.
read -r -d '' READ_PLACEMENTS <<'EOF' || true
img=/etc/timelike/announcement.md
cc="$HOME/.claude/CLAUDE.md"
cx="${CODEX_HOME:-$HOME/.codex}/AGENTS.md"
oc="$HOME/.config/opencode/AGENTS.md"
sha() { if [ -f "$1" ]; then sha256sum <"$1" | cut -d" " -f1; else printf "<absent>"; fi; }
nlines() { if [ -f "$1" ]; then awk "END { print NR }" "$1"; else printf "<absent>"; fi; }
printf "home=%s\n" "$HOME"
printf "image.sha=%s\n" "$(sha "$img")"
printf "image.lines=%s\n" "$(nlines "$img")"
printf "theirs.sha=%s\n" "$(printf "%s\n" "$SC1_THEIRS" | sha256sum | cut -d" " -f1)"
for pair in "claude-code=$cc" "codex=$cx" "opencode=$oc"; do
  h="${pair%%=*}"
  f="${pair#*=}"
  printf "path.%s=%s\n" "$h" "$f"
  printf "sha.%s=%s\n" "$h" "$(sha "$f")"
  printf "lines.%s=%s\n" "$h" "$(nlines "$f")"
done
pid="$(pgrep -x -P 1 sleep | head -n 1)"
ws="$(readlink "/proc/${pid:-0}/cwd" 2>/dev/null || printf "<unreadable>")"
printf "workspace=%s\n" "$ws"
for n in CLAUDE.md AGENTS.md; do
  if [ -e "$ws/$n" ] || [ -L "$ws/$n" ]; then printf "ws.%s=present\n" "$n"; else printf "ws.%s=absent\n" "$n"; fi
done
if [ -d "$ws/.git" ]; then
  g="$(git -C "$ws" status --porcelain --ignored --untracked-files=all 2>&1 | tr "\n" " ")"
  printf "ws.git=%s\n" "${g:-<clean>}"
else
  printf "ws.git=<not a repository>\n"
fi
/opt/timelike/python/bin/python3 -I -c '
import calendar, os, re, sys, time
m = re.match(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9})\d*)?Z$", sys.argv[1])
if not m:
    print("placed_first_ms=<StartedAt unparseable: %s>" % sys.argv[1])
    raise SystemExit(0)
start = calendar.timegm(time.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")) * 10**9
start += int((m.group(2) or "0").ljust(9, "0"))
ms = []
for p in sys.argv[2:]:
    try:
        ms.append((os.stat(p).st_mtime_ns - start) // 10**6)
    except OSError:
        print("placed_first_ms=<absent: %s>" % p)
        raise SystemExit(0)
print("placed_first_ms=%d" % min(ms))
print("placed_last_ms=%d" % max(ms))
' "$SC1_STARTED_AT" "$cc" "$cx" "$oc"
st="$(mktemp)"
timelike announce --status --json >"$st" 2>"$st.err"
printf "status_rc=%s\n" "$?"
printf "status_err=%s\n" "$(head -c 300 "$st.err" | tr "\n" " ")"
/opt/timelike/python/bin/python3 -I -c '
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        doc = json.load(fh)
except (OSError, ValueError) as exc:
    print("status_json=invalid: %s" % exc)
    raise SystemExit(0)
print("status_json=ok")
ps = doc.get("placements") if isinstance(doc, dict) else None
if not isinstance(ps, list):
    print("placements=<absent>")
    raise SystemExit(0)
print("placements=%d" % len(ps))
for p in ps:
    if not isinstance(p, dict):
        continue
    h = p.get("harness")
    print("state.%s=%s" % (h, p.get("state")))
    print("status_path.%s=%s" % (h, p.get("path")))
    print("reason.%s=%s" % (h, "" if p.get("reason") is None else p.get("reason")))
' "$st"
rm -f "$st" "$st.err"
printf "read=done\n"
EOF

# run_placements fresh|prepared STYLE TTY
run_placements() {
  local name started
  if [[ "$1" == fresh ]]; then
    name="$SC1_FRESH" started="$SC1_FRESH_STARTED"
  else
    name="$SC1_PREPARED" started="$SC1_PREPARED_STARTED"
  fi
  AGENT_CONTAINER="$name" run_in -e "SC1_STARTED_AT=${started}" -e "SC1_THEIRS=${SC1_THEIRS}" \
    "$2" "$3" "$READ_PLACEMENTS"
  assert_within 20
  assert_status 0
  assert_value read "done"
}

# assert_at_most_60 KEY — KEY's value is a line count from 1 to 60.
assert_at_most_60() {
  local n
  n="$(value_of "$1")"
  if ! [[ "$n" =~ ^[0-9]+$ ]] || ((n < 1 || n > 60)); then
    printf '%s: expected 1 to 60 lines, got %q; output:\n%s\n' "$1" "$n" "$output" >&2
    return 1
  fi
}

# assert_announcement_read — the image's announcement exists and is at most 60 lines.
assert_announcement_read() {
  if [[ "$(value_of image.sha)" == "<absent>" ]]; then
    printf '/etc/timelike/announcement.md is absent from the image; output:\n%s\n' "$output" >&2
    return 1
  fi
  assert_at_most_60 image.lines
}

# assert_placed H — H's user-level file is the image's announcement, and --status says `current` there.
assert_placed() {
  local h="$1"
  if [[ "$(value_of "sha.$h")" != "$(value_of image.sha)" ]]; then
    printf '%s: %s is not byte-identical to /etc/timelike/announcement.md (sha256 %s vs %s); output:\n%s\n' \
      "$h" "$(value_of "path.$h")" "$(value_of "sha.$h")" "$(value_of image.sha)" "$output" >&2
    return 1
  fi
  assert_at_most_60 "lines.$h"
  assert_value "state.$h" current
  assert_value "status_path.$h" "$(value_of "path.$h")"
}

assert_status_read() {
  assert_value status_rc 0
  assert_value status_json ok
  assert_value placements "${#SC1_HARNESSES[@]}"
}

# --- fresh start: the user-level part ----------------------------------------------------------------
check_user_level() {
  sc1_ready fresh
  run_placements fresh "$1" "$2"
  assert_announcement_read
  assert_status_read
  local h
  for h in "${SC1_HARNESSES[@]}"; do
    assert_placed "$h"
  done
  if [[ -n "${SC1_BAKED// /}" ]]; then
    printf 'the image itself (entrypoint overridden) already holds %s: presence after start proves nothing about placement on start\n' "$SC1_BAKED" >&2
    return 1
  fi
  local first last
  first="$(value_of placed_first_ms)"
  last="$(value_of placed_last_ms)"
  if ! [[ "$first" =~ ^-?[0-9]+$ && "$last" =~ ^-?[0-9]+$ ]]; then
    printf 'cannot time the placement (first %q, last %q; StartedAt %q); output:\n%s\n' \
      "$first" "$last" "$SC1_FRESH_STARTED" "$output" >&2
    return 1
  fi
  if ((first <= -1000)); then
    printf 'a placed file predates the container start (StartedAt %s) by %s ms: not placed on this start\n' \
      "$SC1_FRESH_STARTED" "$((-first))" >&2
    return 1
  fi
  if ((last >= 1000)); then
    printf 'placement finished %s ms after the container started (StartedAt %s); the bound is 1 s\n' \
      "$last" "$SC1_FRESH_STARTED" >&2
    return 1
  fi
}

# --- prepared start: an existing file is not overwritten ---------------------------------------------
check_existing_kept() {
  sc1_ready prepared
  run_placements prepared "$1" "$2"
  assert_announcement_read
  assert_status_read
  local theirs state
  theirs="$(value_of theirs.sha)"
  if [[ "$(value_of sha.claude-code)" != "$theirs" ]]; then
    printf 'the existing %s was changed (sha256 %s, was %s; the announcement is %s); output:\n%s\n' \
      "$(value_of path.claude-code)" "$(value_of sha.claude-code)" "$theirs" "$(value_of image.sha)" "$output" >&2
    return 1
  fi
  state="$(value_of state.claude-code)"
  if [[ "$state" != "not placed" && "$state" != "not placed: "?* ]]; then
    printf 'state.claude-code: expected "not placed" (someone else'"'"'s file), got %q; output:\n%s\n' "$state" "$output" >&2
    return 1
  fi
  if [[ "$state" == "not placed" && -z "$(value_of reason.claude-code)" ]]; then
    printf '"not placed" for claude-code names no reason (contract: not placed: <reason>); output:\n%s\n' "$output" >&2
    return 1
  fi
  assert_value status_path.claude-code "$(value_of path.claude-code)"
  assert_placed codex
  assert_placed opencode
}

# --- the workspace part: NOT built (D-1) — asserted absent, so the narrowing is visible -------------
check_workspace_untouched() {
  sc1_ready fresh
  sc1_ready prepared
  run_placements fresh "$1" "$2"
  if [[ -z "$SC1_WORKDIR" || "$(value_of workspace)" != "$SC1_WORKDIR" ]]; then
    printf 'fresh: the command'"'"'s working directory is %q, expected the image'"'"'s WORKDIR %q\n' \
      "$(value_of workspace)" "$SC1_WORKDIR" >&2
    return 1
  fi
  assert_value ws.CLAUDE.md absent
  assert_value ws.AGENTS.md absent

  run_placements prepared "$1" "$2"
  assert_value workspace "$(value_of home)/work"
  assert_value ws.CLAUDE.md absent
  assert_value ws.AGENTS.md absent
  assert_value ws.git "<clean>"
}

@test "SC-1 [bash -c, notty] On container start, a timelike announcement of at most 60 lines is present in each supported harness's user-level context location and in the workspace's agent context file when none exists, without overwriting an existing one — fresh start: each user-level file is the image's announcement, at most 60 lines, current, placed within 1 s" { check_user_level c notty; }
@test "SC-1 [bash -lc, notty] On container start, a timelike announcement of at most 60 lines is present in each supported harness's user-level context location and in the workspace's agent context file when none exists, without overwriting an existing one — fresh start: each user-level file is the image's announcement, at most 60 lines, current, placed within 1 s" { check_user_level lc notty; }
@test "SC-1 [bash -c, notty] On container start, a timelike announcement of at most 60 lines is present in each supported harness's user-level context location and in the workspace's agent context file when none exists, without overwriting an existing one — an existing non-timelike ~/.claude/CLAUDE.md is left byte for byte and reported not placed; the others are placed" { check_existing_kept c notty; }
@test "SC-1 [bash -lc, notty] On container start, a timelike announcement of at most 60 lines is present in each supported harness's user-level context location and in the workspace's agent context file when none exists, without overwriting an existing one — an existing non-timelike ~/.claude/CLAUDE.md is left byte for byte and reported not placed; the others are placed" { check_existing_kept lc notty; }
@test "SC-1 [bash -c, notty] On container start, a timelike announcement of at most 60 lines is present in each supported harness's user-level context location and in the workspace's agent context file when none exists, without overwriting an existing one — workspace part NOT built (D-1): no CLAUDE.md or AGENTS.md is created in the workspace" { check_workspace_untouched c notty; }
@test "SC-1 [bash -lc, notty] On container start, a timelike announcement of at most 60 lines is present in each supported harness's user-level context location and in the workspace's agent context file when none exists, without overwriting an existing one — workspace part NOT built (D-1): no CLAUDE.md or AGENTS.md is created in the workspace" { check_workspace_untouched lc notty; }
