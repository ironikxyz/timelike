#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # setup_file exports what the @tests read; bats runs each @test in its own subshell by design
# Feature 007 (prompt 04, slice 1), SC-5 (tasks.md T014; spec FR-14 to FR-17a, D-7 to D-9; contract
# § Slice 1, The command-not-found answer):
#   SC-5 "Typing a command that is not installed exits 127 and prints the install command for the package
#        that provides it or the equivalent timelike tool, when either is known"
#
# In the running agent container, from outside (lore cross-stack P005). Nothing here sources the hook
# or sets TIMELIKE_MISSING_COMMANDS: the answer must come from what the image ships.
#
# Expected lines are built by this test FROM THE SHIPPED DATA (cross-stack P004): setup_file reads
# /etc/timelike/missing-commands.tsv out of the container, and sc5_expected formats the rows for a name
# exactly as the contract's table says. No note text is written here. Two names are used because the
# spec names their shape: `tree` (an `instead` row and a `debian` row, spec FR-16) and `jq` (a package
# only). A shipped file in which either lacks that shape fails the cell with the reason.
#
# Line 1 is checked against bash ITSELF, not only against the contract's table: every cell runs the
# same command twice in the same style, once as is and once with SC5_UNSET=1, which makes the same
# first line `unset -f command_not_found_handle` before the name. Same string, same line number, same
# $0, so the second run's stderr is what the shell says without timelike. The first run's stderr must
# be that, with the timelike lines inserted right after bash's not-found line, and nothing else; for
# an unknown name, nothing is inserted, so the two are byte for byte the same (bats strips the final
# newline of both alike). Interactive bash with no terminal prints its own job-control notices on
# stderr; they are the shell's, so they appear in both runs and the comparison carries them.
#
# Claimed styles (FR-14), each in `notty`, the harness's own invocation:
#   bash -c, bash -lc, bash -ic (interactive: $- holds i, so bash's line has no "line N"), and a script
#   file run with `bash FILE` from bash -c (its own bash reads BASH_ENV; bash names the file in line 1).
# Not reached, asserted as such (FR-14, D-7): `sh -c` (dash: `sh: 1: NAME: not found`) and a direct
# `docker exec` of the missing binary (the kernel's ENOENT, reported by the runtime through docker).
# Then: every listed name is absent and every `instead` resolves; the handler reads no stdin, asks
# nothing (a terminal nobody types into) and installs nothing.

load helpers

SC5_TSV_PATH=/etc/timelike/missing-commands.tsv

setup_file() {
  stamp_check
  SC5_ERROR=""
  SC5_TSV=""
  SC5_DIR=""
  SC5_UNKNOWN="timelike-absent-${RANDOM}-$$"
  sc5_prepare || true
  export SC5_ERROR SC5_TSV SC5_DIR SC5_UNKNOWN
}

teardown_file() {
  container_rm "${SC5_DIR:-}"
}

# sc5_prepare — read the shipped data, check the unknown name is absent, and write one script per name
# (for the script style). On any problem sets SC5_ERROR, so every cell fails with the reason.
sc5_prepare() {
  local out name
  out="$(exec_plain cat "$SC5_TSV_PATH" 2>&1)" || {
    SC5_ERROR="cannot read ${SC5_TSV_PATH} in ${AGENT_CONTAINER}: ${out}"
    return 1
  }
  SC5_TSV="$out"
  if exec_plain bash -c 'command -v -- "$1"' sc5 "$SC5_UNKNOWN" >/dev/null 2>&1; then
    SC5_ERROR="the 'unknown' name ${SC5_UNKNOWN} resolves in the container: pick another"
    return 1
  fi
  SC5_DIR="$(container_tmpdir sc5)" || {
    SC5_ERROR="cannot make a directory under /tmp in ${AGENT_CONTAINER}"
    return 1
  }
  # Line 1 of each script is the same toggle the inline styles use, so bash reports line 1 either way.
  for name in tree jq "$SC5_UNKNOWN"; do
    exec_plain sh -c 'printf "%s\n" "[ -z \"\${SC5_UNSET:-}\" ] || unset -f command_not_found_handle; $2" >"$1"' \
      sc5 "${SC5_DIR}/${name}.sh" "$name" || {
      SC5_ERROR="cannot write ${SC5_DIR}/${name}.sh in ${AGENT_CONTAINER}"
      return 1
    }
  done
}

sc5_ready() {
  if [[ -n "${SC5_ERROR:-}" ]]; then
    echo "SC-5 precondition: ${SC5_ERROR}" >&2
    return 1
  fi
}

# sc5_typed NAME — the command line every inline cell types: the toggle, then the name, on line 1.
sc5_typed() {
  printf '[ -z "${SC5_UNSET:-}" ] || unset -f command_not_found_handle; %s' "$1"
}

# sc5_expected NAME — sets SC5_WANT to the timelike lines the contract gives NAME, from the shipped rows
# in file order, and SC5_KINDS to their kinds (space-separated). Rules (contract § The data): `#` lines
# and empty lines ignored; exactly four tab-separated fields, else skipped; an unknown kind skipped.
# ASSUMED: "the <note> part omitted when the note is -" drops the two spaces with the parentheses.
sc5_expected() {
  local want="$1" line tabs name kind value note rest
  SC5_WANT=()
  SC5_KINDS=""
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" == "#"* ]] && continue
    tabs="${line//[!$'\t']/}"
    ((${#tabs} == 3)) || continue
    name="${line%%$'\t'*}"
    rest="${line#*$'\t'}"
    kind="${rest%%$'\t'*}"
    rest="${rest#*$'\t'}"
    value="${rest%%$'\t'*}"
    note="${rest#*$'\t'}"
    [[ "$name" == "$want" ]] || continue
    case "$kind" in
      instead)
        if [[ "$note" == - ]]; then SC5_WANT+=("timelike: instead: ${value}"); else SC5_WANT+=("timelike: instead: ${value}  (${note})"); fi
        ;;
      debian)
        SC5_WANT+=("timelike: ${name} is in the Debian package ${value}, which is not installed. The agent cannot install OS packages (no root): the operator adds ${value} to the image.")
        ;;
      user)
        if [[ "$note" == - ]]; then SC5_WANT+=("timelike: install it yourself: ${value}"); else SC5_WANT+=("timelike: install it yourself: ${value}  (${note})"); fi
        ;;
      *) continue ;;
    esac
    SC5_KINDS+=" ${kind}"
  done <<<"$SC5_TSV"
}

# sc5_shape WHICH NAME — the shipped rows for NAME have the shape this cell is about.
sc5_shape() {
  case "$1" in
    tree)
      if [[ "$SC5_KINDS" != *" instead"* || "$SC5_KINDS" != *" debian"* ]]; then
        printf '%s: the shipped %s has no instead row and debian row for tree (kinds:%s); spec FR-16 names both\n' \
          "$2" "$SC5_TSV_PATH" "${SC5_KINDS:- none}" >&2
        return 1
      fi
      ;;
    jq)
      if [[ "$SC5_KINDS" != *" debian"* || "$SC5_KINDS" == *" instead"* ]]; then
        printf '%s: the shipped %s does not give jq a Debian package and no equivalent (kinds:%s)\n' \
          "$2" "$SC5_TSV_PATH" "${SC5_KINDS:- none}" >&2
        return 1
      fi
      ;;
    unknown)
      if ((${#SC5_WANT[@]} != 0)); then
        printf '%s: the shipped %s lists the unknown name %s\n' "$2" "$SC5_TSV_PATH" "$2" >&2
        return 1
      fi
      ;;
  esac
}

# run_sep FLAG [-e K=V]... STYLE TTY CMD — run_in with stdout and stderr kept apart: $output and
# ${lines[@]} are stdout, $stderr and ${stderr_lines[@]} are stderr, empty lines kept. FLAG is bats'
# own status check (-127, or ! for any non-zero), so a wrong status fails at the call with the output.
run_sep() {
  local flag="$1" start end
  shift
  start=$(now_ms)
  run "$flag" --keep-empty-lines --separate-stderr exec_in "$@"
  end=$(now_ms)
  ELAPSED_MS=$((end - start))
  # shellcheck disable=SC2034 # read by helpers.bash assert_within/assert_status
  ELAPSED_S="$(ms_to_s "$ELAPSED_MS")"
}

# assert_no_timelike_line — neither stream has a line starting `timelike:`.
assert_no_timelike_line() {
  local line
  for line in "${lines[@]}" "${stderr_lines[@]}"; do
    if [[ "$line" == timelike:* ]]; then
      printf 'unexpected timelike line: %s\nstdout:\n%s\nstderr:\n%s\n' "$line" "$output" "$stderr" >&2
      return 1
    fi
  done
}

# --- the claimed styles -----------------------------------------------------------------------------
# check_answer STYLE WHICH — STYLE c | lc | ic | script; WHICH tree | jq | unknown.
check_answer() {
  local style="$1" which="$2" name cmd run_style want_bash
  sc5_ready
  if [[ "$which" == unknown ]]; then name="$SC5_UNKNOWN"; else name="$which"; fi
  sc5_expected "$name"
  sc5_shape "$which" "$name"
  case "$style" in
    script)
      run_style=c
      cmd="bash ${SC5_DIR}/${name}.sh"
      want_bash="${SC5_DIR}/${name}.sh: line 1: ${name}: command not found"
      ;;
    ic)
      run_style=ic
      cmd="$(sc5_typed "$name")"
      want_bash="bash: ${name}: command not found"
      ;;
    *)
      run_style="$style"
      cmd="$(sc5_typed "$name")"
      want_bash="bash: line 1: ${name}: command not found"
      ;;
  esac

  # Without the handler: what bash itself says, in the same style, from the same line.
  run_sep -127 -e SC5_UNSET=1 "$run_style" notty "$cmd"
  local -a base=("${stderr_lines[@]}")
  local base_err="$stderr" i at=-1
  for i in "${!base[@]}"; do
    if [[ "${base[$i]}" == "$want_bash" ]]; then
      at="$i"
      break
    fi
  done
  if ((at < 0)); then
    printf 'control run (handler unset): bash did not print %q; stderr:\n%s\n' "$want_bash" "$base_err" >&2
    return 1
  fi
  if [[ "$style" != ic ]] && ((${#base[@]} != 1)); then
    printf 'control run (handler unset): expected bash'"'"'s one line on stderr, got:\n%s\n' "$base_err" >&2
    return 1
  fi

  # With the handler: bash's line, then the timelike lines, nothing else changed.
  run_sep -127 "$run_style" notty "$cmd"
  assert_within 10
  if [[ -n "$output" ]]; then
    printf 'the handler wrote to stdout (contract: stderr only):\n%s\n' "$output" >&2
    return 1
  fi
  local -a want=("${base[@]:0:at+1}" "${SC5_WANT[@]}" "${base[@]:at+1}")
  local ok=1
  if ((${#stderr_lines[@]} != ${#want[@]})); then
    ok=0
  else
    for i in "${!want[@]}"; do
      [[ "${stderr_lines[$i]}" == "${want[$i]}" ]] || ok=0
    done
  fi
  if ((ok == 0)); then
    printf 'stderr differs from bash'"'"'s own with the timelike lines after line %d.\nwant (%d lines):\n' \
      "$((at + 1))" "${#want[@]}" >&2
    printf '  %q\n' "${want[@]}" >&2
    printf 'got (%d lines):\n' "${#stderr_lines[@]}" >&2
    printf '  %q\n' "${stderr_lines[@]}" >&2
    return 1
  fi
}

@test "SC-5 [bash -c, notty] Typing a command that is not installed exits 127 and prints the install command for the package that provides it or the equivalent timelike tool, when either is known — tree: bash's own line, then the equivalent and the Debian package, from the shipped rows" { check_answer c tree; }
@test "SC-5 [bash -c, notty] Typing a command that is not installed exits 127 and prints the install command for the package that provides it or the equivalent timelike tool, when either is known — jq: bash's own line, then the Debian package, from the shipped rows" { check_answer c jq; }
@test "SC-5 [bash -c, notty] Typing a command that is not installed exits 127 and prints the install command for the package that provides it or the equivalent timelike tool, when either is known — an unknown name: stderr byte for byte as with the handler unset" { check_answer c unknown; }
@test "SC-5 [bash -lc, notty] Typing a command that is not installed exits 127 and prints the install command for the package that provides it or the equivalent timelike tool, when either is known — tree: bash's own line, then the equivalent and the Debian package, from the shipped rows" { check_answer lc tree; }
@test "SC-5 [bash -lc, notty] Typing a command that is not installed exits 127 and prints the install command for the package that provides it or the equivalent timelike tool, when either is known — jq: bash's own line, then the Debian package, from the shipped rows" { check_answer lc jq; }
@test "SC-5 [bash -lc, notty] Typing a command that is not installed exits 127 and prints the install command for the package that provides it or the equivalent timelike tool, when either is known — an unknown name: stderr byte for byte as with the handler unset" { check_answer lc unknown; }
@test "SC-5 [bash -ic, notty] Typing a command that is not installed exits 127 and prints the install command for the package that provides it or the equivalent timelike tool, when either is known — tree: bash's own line, then the equivalent and the Debian package, from the shipped rows" { check_answer ic tree; }
@test "SC-5 [bash -ic, notty] Typing a command that is not installed exits 127 and prints the install command for the package that provides it or the equivalent timelike tool, when either is known — jq: bash's own line, then the Debian package, from the shipped rows" { check_answer ic jq; }
@test "SC-5 [bash -ic, notty] Typing a command that is not installed exits 127 and prints the install command for the package that provides it or the equivalent timelike tool, when either is known — an unknown name: stderr byte for byte as with the handler unset" { check_answer ic unknown; }
@test "SC-5 [bash FILE, from bash -c, notty] Typing a command that is not installed exits 127 and prints the install command for the package that provides it or the equivalent timelike tool, when either is known — tree in a script: the script's own line, then the equivalent and the Debian package, from the shipped rows" { check_answer script tree; }
@test "SC-5 [bash FILE, from bash -c, notty] Typing a command that is not installed exits 127 and prints the install command for the package that provides it or the equivalent timelike tool, when either is known — jq in a script: the script's own line, then the Debian package, from the shipped rows" { check_answer script jq; }
@test "SC-5 [bash FILE, from bash -c, notty] Typing a command that is not installed exits 127 and prints the install command for the package that provides it or the equivalent timelike tool, when either is known — an unknown name in a script: stderr byte for byte as with the handler unset" { check_answer script unknown; }

# --- the styles it does not reach, asserted as such (FR-14, D-7) ------------------------------------
check_sh_not_reached() {
  sc5_ready
  run_sep -127 sh notty tree
  assert_within 10
  if [[ "$stderr" != "sh: 1: tree: not found" ]]; then
    printf 'sh -c: expected dash'"'"'s own %q on stderr, got:\n%s\n' "sh: 1: tree: not found" "$stderr" >&2
    return 1
  fi
  assert_no_timelike_line
}

# A direct exec has no shell: runc's execve fails with ENOENT and docker prints the runtime's error,
# of the form `OCI runtime exec failed: exec failed: unable to start container process: exec: "tree":
# executable file not found in $PATH: unknown`. Its exit status is docker's own: 127 on current
# releases, 126 on some older ones (read from docker's behaviour as recalled, NOT verified here — no
# daemon), so the cell asserts non-zero and prints what it got.
direct_exec() {
  timeout "$RUN_TIMEOUT" docker exec "$AGENT_CONTAINER" "$1" </dev/null
}

check_direct_exec_not_reached() {
  sc5_ready
  run ! --keep-empty-lines --separate-stderr direct_exec tree
  if [[ "$stderr" != *tree* || "$stderr" != *"not found"* ]]; then
    printf 'direct exec (exit %s): expected docker'"'"'s not-found message naming tree, got:\n%s\n' "$status" "$stderr" >&2
    return 1
  fi
  assert_no_timelike_line
}

@test "SC-5 [sh -c, notty] Typing a command that is not installed exits 127 and prints the install command for the package that provides it or the equivalent timelike tool, when either is known — not reached (D-7): exit 127, dash's own line, no timelike line" { check_sh_not_reached; }
@test "SC-5 [direct docker exec] Typing a command that is not installed exits 127 and prints the install command for the package that provides it or the equivalent timelike tool, when either is known — not reached (FR-14): docker's own not-found error, non-zero, no timelike line" { check_direct_exec_not_reached; }

# --- the data against the image (FR-16, contract § e2e) ---------------------------------------------
read -r -d '' READ_LISTED <<'EOF' || true
f=/etc/timelike/missing-commands.tsv
if [ ! -r "$f" ]; then printf "tsv=unreadable\n"; exit 0; fi
n=0
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in "" | "#"*) continue ;; esac
  name="${line%%$'\t'*}"
  rest="${line#*$'\t'}"
  kind="${rest%%$'\t'*}"
  rest="${rest#*$'\t'}"
  value="${rest%%$'\t'*}"
  n=$((n + 1))
  if p="$(command -v -- "$name")"; then printf "installed=%s at %s\n" "$name" "$p"; fi
  if [ "$kind" = instead ]; then
    w="${value%% *}"
    if p="$(command -v -- "$w")"; then
      case "$p" in /opt/timelike/bin/*) ;; *) printf "instead_not_timelike=%s (for %s) resolves to %s\n" "$w" "$name" "$p" ;; esac
    else
      printf "instead_missing=%s (for %s)\n" "$w" "$name"
    fi
  fi
done <"$f"
printf "rows=%s\n" "$n"
printf "read=done\n"
EOF

check_listed_absent() {
  sc5_ready
  run_in c notty "$READ_LISTED"
  assert_within 20
  assert_status 0
  assert_value read "done"
  local rows
  rows="$(value_of rows)"
  if ! [[ "$rows" =~ ^[0-9]+$ ]] || ((rows < 1)); then
    printf '%s lists no rows (rows=%s); output:\n%s\n' "$SC5_TSV_PATH" "$rows" "$output" >&2
    return 1
  fi
  assert_no_line_matching '^installed='
  assert_no_line_matching '^instead_missing='
  assert_no_line_matching '^instead_not_timelike='
}

@test "SC-5 [bash -c, notty] Typing a command that is not installed exits 127 and prints the install command for the package that provides it or the equivalent timelike tool, when either is known — every listed name is absent in the image, and every equivalent's first word is a timelike tool on PATH" { check_listed_absent; }

# --- never reads stdin, never asks, never installs (FR-15; P2, P4) ----------------------------------
# stdin is /dev/zero (endless, never a newline): a handler that read it would never finish, and the
# runner's bound turns that into a failure. Then the names must still be absent, and nothing new may
# exist under $HOME (the journal's record goes to the scratch root under /tmp, not $HOME).
read -r -d '' READ_NO_STDIN <<'EOF' || true
m="$(mktemp)"
tree </dev/zero 2>/dev/null
printf "tree_rc=%s\n" "$?"
jq </dev/zero 2>/dev/null
printf "jq_rc=%s\n" "$?"
printf "new_in_home=%s\n" "$(find "$HOME" -newer "$m" -print 2>/dev/null | head -n 5 | tr "\n" " ")"
printf "tree_after=%s\n" "$(command -v tree || printf "<absent>")"
printf "jq_after=%s\n" "$(command -v jq || printf "<absent>")"
rm -f "$m"
printf "read=done\n"
EOF

check_no_stdin_no_install() {
  sc5_ready
  run_in c notty "$READ_NO_STDIN"
  assert_within 10
  assert_status 0
  assert_value read "done"
  assert_value tree_rc 127
  assert_value jq_rc 127
  assert_value new_in_home ""
  assert_value tree_after "<absent>"
  assert_value jq_after "<absent>"
}

# On a terminal nobody types into (helpers.bash `tty`): a handler that asked would wait forever.
check_no_prompt_on_tty() {
  sc5_ready
  sc5_expected tree
  sc5_shape tree tree
  run_in c tty tree
  assert_within 10
  assert_status 127
  local -a want=("bash: line 1: tree: command not found" "${SC5_WANT[@]}")
  if [[ "$(printf '%s\n' "${lines[@]}")" != "$(printf '%s\n' "${want[@]}")" ]]; then
    printf 'on a tty, expected:\n' >&2
    printf '  %q\n' "${want[@]}" >&2
    printf 'got:\n' >&2
    printf '  %q\n' "${lines[@]}" >&2
    return 1
  fi
}

@test "SC-5 [bash -c, notty] Typing a command that is not installed exits 127 and prints the install command for the package that provides it or the equivalent timelike tool, when either is known — the handler reads no stdin and installs nothing: 127 promptly with stdin endless, names still absent, nothing new under \$HOME" { check_no_stdin_no_install; }
@test "SC-5 [bash -c, tty] Typing a command that is not installed exits 127 and prints the install command for the package that provides it or the equivalent timelike tool, when either is known — the handler asks nothing: on a terminal nobody types into, tree concludes with 127 and the same lines" { check_no_prompt_on_tty; }
