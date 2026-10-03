#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-3 — "A git operation that would need credentials fails fast with a non-zero exit instead of
# prompting." (tasks.md T021; spec FR-3; research R2.)
#
# Cycle 5 (discovery revision 7): SC-3's hooks clause is struck, and this file's hooks half is gone
# with it. It asserted that repository hooks do not run; they now run, bounded (tension T4, research
# R11). Their tests are hooks-a-repository-configures-run.bats (SC-12) and
# hook-past-its-time-limit-is-killed.bats (SC-13). The file was credentials-fail-fast-and-hooks-off.bats.
#
# Credentials, without the internet: fixtures/http401.py runs INSIDE the container on 127.0.0.1 and
# answers every request with 401 + WWW-Authenticate, which is what makes git look for a username.
# Its request log is read after each run, so a fast failure is shown to be a refused credential
# prompt and not a network error (lore cross-stack P004; tasks.md T021: "a network failure is not a
# credential prompt"). The https case of T021 is covered by this plain-http challenge: git's
# credential path (helper → askpass → terminal prompt) is the same for both schemes, and a local
# fixture needs no certificate. No test is skipped for lack of network.
#
# ssh: there is no ssh client in the image (stack note 15, discovery revision 5: under P4 the agent
# holds no SSH keys, so credentialed git goes over https through Adele). git over ssh therefore still
# concludes fast with a non-zero exit and no prompt, and the output shows why: git could not run ssh.
# The control is read directly too: no `ssh` is on PATH under any invocation style. This replaces the
# BatchMode check of cycle 1, which needed an ssh client to read its effective configuration.
#
# Each run: < 10 s measured, not a timeout, non-zero, and no prompt line in the output. In `tty` mode
# a prompt would block on the terminal and time out (124); in `pty` mode script may feed it an EOF, so
# the absence of the prompt text is asserted too (helpers.bash).
#
# Common failures (slice 1, natural intensity; modify.md F005; tasks.md T053), each confirmed locally
# against this fixture with the image's ENV and /etc/gitconfig:
#   - a URL with an embedded username (http://agent@host/...): git skips the username and asks for a
#     PASSWORD, a different prompt from the one above. Refused: rc 128, "could not read Password".
#   - git clone, the usual first contact with a remote, not only ls-remote: rc 128, and git removes
#     the half-made directory, so no empty clone is left for the agent to mistake for a repository.
# Cells: bash -c and bash -lc, the harness's invocations (spec Assumption 1), in `tty` mode, where a
# prompt would block on the terminal (124). Whether the defaults reach each style and mode is proven by the
# happy-path matrix above and by SC-2; these cells prove the defaults cover another path.
# Not added: a credential helper in the repository's own .git/config. A clone never carries config,
# so such a helper is the agent's own explicit choice, which the spec leaves in effect.

load helpers

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/http401.py" /tmp/sc3-http401.py
  SC3_STATE="$(container_tmpdir sc3srv)"
  timeout "$RUN_TIMEOUT" docker exec -d "$AGENT_CONTAINER" \
    "$AGENT_PY" -I /tmp/sc3-http401.py "$SC3_STATE" </dev/null
  local server=""
  for _ in $(seq 1 50); do
    server="$(exec_plain cat "${SC3_STATE}/server" 2>/dev/null)" && break
    sleep 0.2
  done
  if [[ -z "$server" ]]; then
    echo "SC-3 fixture: the 401 server did not start (no ${SC3_STATE}/server after 10 s)" >&2
    return 1
  fi
  SC3_PID="${server%% *}"
  SC3_PORT="${server##* }"
  SC3_PORT="${SC3_PORT//[!0-9]/}"
  [[ -n "$SC3_PORT" ]] || { echo "SC-3 fixture: bad server file '$server'" >&2; return 1; }
  export SC3_STATE SC3_PID SC3_PORT
}

teardown_file() {
  if [[ -n "${SC3_PID:-}" ]]; then
    exec_plain kill "$SC3_PID" >/dev/null 2>&1 || true
  fi
  container_rm "${SC3_STATE:-}"
}

setup() {
  WORK=""
}

teardown() {
  kill_strays
  container_rm "$WORK"
}

# request_count — lines in the 401 server's request log (0 before the first request).
request_count() {
  local log
  log="$(exec_plain cat "${SC3_STATE}/requests" 2>/dev/null)" || { echo 0; return; }
  if [[ -z "$log" ]]; then echo 0; else wc -l <<<"$log" | tr -d ' '; fi
}

assert_failed_fast_without_prompt() {
  assert_within 10
  if [[ "$status" == 0 ]]; then
    printf 'expected a non-zero exit, got 0; output:\n%s\n' "$output" >&2
    return 1
  fi
  # A prompt line starts with the question; git's refusal starts with "fatal: could not read ...".
  assert_no_line_matching "^(Username|Password) for '"
  assert_no_line_matching "^Enter passphrase"
  assert_no_line_matching "yes/no"
  assert_no_line_matching "[Pp]assword: *$"
}

check_https_credentials() {
  local before after
  before="$(request_count)"
  run_in "$1" "$2" "git ls-remote http://127.0.0.1:${SC3_PORT}/repo.git"
  assert_failed_fast_without_prompt
  after="$(request_count)"
  if ((after <= before)); then
    printf 'the credential server saw no request (%s → %s): this failure is not a credential refusal; output:\n%s\n' \
      "$before" "$after" "$output" >&2
    return 1
  fi
}

check_ssh_no_client() {
  run_in "$1" "$2" "git ls-remote ssh://git@127.0.0.1:1/repo.git"
  assert_failed_fast_without_prompt
  # The cause, not just the speed: a refused connection would mean an ssh client ran after all.
  # git's run-command says "cannot run ssh: No such file or directory" when the client is missing.
  assert_output_has "cannot run ssh"
}

check_no_ssh_on_path() {
  # Prints the path it found, if any, so a failure names the ssh that crept back in.
  run_in "$1" notty 'if command -v ssh; then exit 1; fi; echo "no ssh on PATH"'
  assert_within 10
  assert_status 0
  assert_output_has "no ssh on PATH"
}

# The URL names the user, so git asks only for the password; the refusal must name that prompt.
check_embedded_username() {
  local before after
  before="$(request_count)"
  run_in "$1" "$2" "git ls-remote http://agent@127.0.0.1:${SC3_PORT}/repo.git"
  assert_failed_fast_without_prompt
  assert_output_has "could not read Password"
  after="$(request_count)"
  ((after > before)) || { printf 'the credential server saw no request (%s → %s); output:\n%s\n' "$before" "$after" "$output" >&2; return 1; }
}

check_clone_credentials() {
  local before after
  WORK="$(container_tmpdir sc3clone)"
  before="$(request_count)"
  run_in "$1" "$2" "cd '${WORK}' && git clone http://127.0.0.1:${SC3_PORT}/repo.git cloned"
  assert_failed_fast_without_prompt
  assert_output_has "could not read Username"
  after="$(request_count)"
  ((after > before)) || { printf 'the credential server saw no request (%s → %s); output:\n%s\n' "$before" "$after" "$output" >&2; return 1; }
  # Artefact: no half-made clone left behind.
  run exec_plain test -e "${WORK}/cloned"
  [[ "$status" -ne 0 ]] || { echo "git clone left ${WORK}/cloned behind after failing" >&2; return 1; }
}

# --- credentials: http 401 challenge ---
@test "SC-3 git credential need fails fast with non-zero exit instead of prompting: http 401 [bash -c, notty]" { check_https_credentials c notty; }
@test "SC-3 git credential need fails fast with non-zero exit instead of prompting: http 401 [bash -c, tty]" { check_https_credentials c tty; }
@test "SC-3 git credential need fails fast with non-zero exit instead of prompting: http 401 [bash -c, pty]" { check_https_credentials c pty; }
@test "SC-3 git credential need fails fast with non-zero exit instead of prompting: http 401 [bash -lc, notty]" { check_https_credentials lc notty; }
@test "SC-3 git credential need fails fast with non-zero exit instead of prompting: http 401 [bash -lc, tty]" { check_https_credentials lc tty; }
@test "SC-3 git credential need fails fast with non-zero exit instead of prompting: http 401 [bash -lc, pty]" { check_https_credentials lc pty; }
@test "SC-3 git credential need fails fast with non-zero exit instead of prompting: http 401 [bash -ic, notty]" { check_https_credentials ic notty; }
@test "SC-3 git credential need fails fast with non-zero exit instead of prompting: http 401 [bash -ic, tty]" { check_https_credentials ic tty; }
@test "SC-3 git credential need fails fast with non-zero exit instead of prompting: http 401 [bash -ic, pty]" { check_https_credentials ic pty; }

# --- ssh: no client in the image (stack note 15) ---
@test "SC-3 git over ssh fails fast with non-zero exit and no prompt: no ssh client in the image [bash -c, notty]" { check_ssh_no_client c notty; }
@test "SC-3 git over ssh fails fast with non-zero exit and no prompt: no ssh client in the image [bash -c, tty]" { check_ssh_no_client c tty; }
@test "SC-3 git over ssh fails fast with non-zero exit and no prompt: no ssh client in the image [bash -c, pty]" { check_ssh_no_client c pty; }
@test "SC-3 git over ssh fails fast with non-zero exit and no prompt: no ssh client in the image [bash -lc, notty]" { check_ssh_no_client lc notty; }
@test "SC-3 git over ssh fails fast with non-zero exit and no prompt: no ssh client in the image [bash -lc, tty]" { check_ssh_no_client lc tty; }
@test "SC-3 git over ssh fails fast with non-zero exit and no prompt: no ssh client in the image [bash -lc, pty]" { check_ssh_no_client lc pty; }
@test "SC-3 git over ssh fails fast with non-zero exit and no prompt: no ssh client in the image [bash -ic, notty]" { check_ssh_no_client ic notty; }
@test "SC-3 git over ssh fails fast with non-zero exit and no prompt: no ssh client in the image [bash -ic, tty]" { check_ssh_no_client ic tty; }
@test "SC-3 git over ssh fails fast with non-zero exit and no prompt: no ssh client in the image [bash -ic, pty]" { check_ssh_no_client ic pty; }

# --- ssh control, read directly ---
@test "SC-3 no ssh client on PATH, so nothing can prompt for an ssh key or host [bash -c]" { check_no_ssh_on_path c; }
@test "SC-3 no ssh client on PATH, so nothing can prompt for an ssh key or host [bash -lc]" { check_no_ssh_on_path lc; }
@test "SC-3 no ssh client on PATH, so nothing can prompt for an ssh key or host [bash -ic]" { check_no_ssh_on_path ic; }
@test "SC-3 no ssh client on PATH, so nothing can prompt for an ssh key or host [sh -c]" { check_no_ssh_on_path sh; }

# --- common failures (slice 1) ---
@test "SC-3 git credential need fails fast with non-zero exit instead of prompting: username in the URL, password refused [bash -c, tty]" { check_embedded_username c tty; }
@test "SC-3 git credential need fails fast with non-zero exit instead of prompting: username in the URL, password refused [bash -lc, tty]" { check_embedded_username lc tty; }
@test "SC-3 git clone that needs credentials fails fast with non-zero exit, no prompt, no half-made clone [bash -c, tty]" { check_clone_credentials c tty; }
@test "SC-3 git clone that needs credentials fails fast with non-zero exit, no prompt, no half-made clone [bash -lc, tty]" { check_clone_credentials lc tty; }
