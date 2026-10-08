#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-10 — "Values matching known secret formats are shown and stored as `[REDACTED:<type>]` in both the
# displayed output and the saved log". (Feature 003, slice 1; spec FR-33 to FR-40, Scenario 7;
# contracts/run-cli.md § Slice 1; research R15, R18.)
#
# No secret-shaped value is a literal in this file, not even a fake one: `make scan`'s gitleaks step
# blocks on any finding in history, and GitHub's push protection would too (spec SC-10). The values
# are generated at run time INSIDE the agent container, by the image's own Python (`secrets`), with
# every provider prefix built by concatenation, and kept in a per-test directory there:
#   - a GitHub PAT-shaped token (rule github-pat, type token);
#   - an AWS access key ID (rule aws-access-token, type credential);
#   - a PEM private key block, 20 random base64 lines between its BEGIN and END lines (rule
#     private-key, type key; a multi-line key counts once).
# The token and the key ID are drawn until their Shannon entropy is at least 3.5 (both rules ask for
# 3), and every filler line and key-body line is drawn clear of every keyword in the image's own rule
# file, so each secret is matched by exactly its own rule and the counts are exactly 1, 1 and 1.
#
# The secrets never travel to the runner, so a failure cannot print one into tests/out: every check
# that touches them runs in the container (`grep -cF -f secrets.txt`, and a checker that prints counts
# and replaces any secret in what it prints by `<generated secret>`).
#
# Each test runs under its own TIMELIKE_SESSION, so its scratch directory holds only its own logs and
# session events: "stored" is checked over that whole directory (FR-36 the log, FR-37 the event's
# arguments), not only the log the verdict names.
# Slice 0 puts `data`'s fields at the top level of the JSON document: `data.log` is the key `log`.
# Cells: bash -c and bash -lc in `notty`.

load helpers

# at_least VALUE MIN — VALUE is a non-negative integer and at least MIN.
at_least() { [[ "$1" =~ ^[0-9]+$ ]] && (($1 >= $2)); }

# The 18 rule ids FR-33 names (names, not values).
RULE_IDS=(anthropic-admin-api-key anthropic-api-key aws-access-token gcp-api-key github-app-token
  github-fine-grained-pat github-oauth github-pat github-refresh-token gitlab-pat jwt npm-access-token
  openai-api-key private-key pypi-upload-token slack-bot-token slack-user-token stripe-access-token)

# gen.py WORK — writes WORK/input.txt (the command's output), WORK/secrets.txt (one secret per line:
# the token, the key ID and each key-body line) and WORK/token.txt (the token alone).
GEN_PY="$(
  cat <<'PY'
import math
import secrets
import string
import sys
import tomllib
from collections import Counter

work = sys.argv[1]
with open("/etc/timelike/redaction.toml", "rb") as fh:
    rules = tomllib.load(fh).get("rules", [])
keywords = sorted({k.lower() for r in rules for k in r.get("keywords", [])})
if not keywords:
    sys.exit("the rule file names no keywords: the filler lines cannot be kept clear of them")


def entropy(s):
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in Counter(s).values())


def clear(s):
    low = s.lower()
    return not any(k in low for k in keywords)


def draw(prefix, alphabet, n):
    while True:
        tail = "".join(secrets.choice(alphabet) for _ in range(n))
        value = prefix + tail
        if clear(tail) and entropy(value) >= 3.5 and not value.endswith("EXAMPLE"):
            return value


token = draw("gh" + "p_", string.ascii_letters + string.digits, 36)
key_id = draw("AK" + "IA", string.ascii_uppercase + "234567", 16)
b64 = string.ascii_letters + string.digits + "+/"
body = []
while len(body) < 20:
    line = "".join(secrets.choice(b64) for _ in range(64))
    if clear(line):
        body.append(line)
kind = "RSA PRI" + "VATE KEY"
filler = ["build: compiling 42 modules", "build: linking", "build: running checks", "build: all checks passed"]
for line in filler:
    if not clear(line):
        sys.exit(f"filler line {line!r} carries a rule keyword")
lines = [
    filler[0],
    "github: " + token,
    filler[1],
    "aws_access_key_id = " + key_id,
    filler[2],
    "-----BEGIN " + kind + "-----",
    *body,
    "-----END " + kind + "-----",
    filler[3],
]
with open(f"{work}/input.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
with open(f"{work}/secrets.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join([token, key_id, *body]) + "\n")
with open(f"{work}/token.txt", "w", encoding="utf-8") as fh:
    fh.write(token + "\n")
print("generated=ok")
print(f"input_lines={len(lines)}")
PY
)"

# check.py MODE OUT WORK — reads run's output OUT (MODE json or text) and the log it names. Prints
# counts and fields as KEY=VALUE lines; any secret in a printed string is replaced first.
CHECK_PY="$(
  cat <<'PY'
import json
import re
import sys

mode, out, work = sys.argv[1:4]
with open(f"{work}/secrets.txt", encoding="utf-8") as fh:
    found = [s for s in fh.read().splitlines() if s]
TYPES = ("credential", "key", "token")


def hits(text):
    return sum(1 for s in found if s in text)


def clean(text):
    for s in found:
        text = text.replace(s, "<generated secret>")
    return text.replace("\n", "\\n")


def marked(rows, kind):
    mark = "[REDACTED:" + kind + "]"
    return sum(1 for x in rows if mark in x)


with open(out, encoding="utf-8", errors="replace") as fh:
    raw = fh.read()
print(f"out_secrets={hits(raw)}")
if mode == "json":
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        print("json=invalid")
        print(f"json_error={clean(str(exc))}")
        sys.exit(0)
    print("json=ok")
    shown = [str(x) for x in doc.get("lines", [])]
    verdict = str(doc.get("verdict", ""))
    log = str(doc.get("log", ""))
    for k in ("exit", "cause", "command_exit"):
        print(f"{k}={doc.get(k, '<absent>')}")
    red = doc.get("redaction")
    red = red if isinstance(red, dict) else {}
    print(f"redaction.state={red.get('state', '<absent>')}")
    print(f"redaction.counts={json.dumps(red.get('counts'), sort_keys=True)}")
    print(f"redaction.log_rewritten={json.dumps(red.get('log_rewritten'))}")
    print(f"target={clean(str(doc.get('target', '')))}")
else:
    rows = raw.splitlines()
    print(f"header={clean(rows[0]) if rows else '<absent>'}")
    verdict = rows[1][len("verdict: "):] if len(rows) > 1 and rows[1].startswith("verdict: ") else ""
    shown = rows[2:]
    m = re.search(r" · log (\S+)", verdict)
    log = m.group(1) if m else ""
print(f"verdict={clean(verdict)}")
print(f"shown_lines={len(shown)}")
for t in TYPES:
    print(f"shown_{t}={marked(shown, t)}")
print(f"log={log or '<absent>'}")
if log:
    try:
        with open(log, "rb") as fh:
            data = fh.read().decode("utf-8", "replace")
    except OSError as exc:
        print(f"log_error={exc.strerror}")
    else:
        print(f"log_lines={data.count(chr(10))}")
        print(f"log_secrets={hits(data)}")
        for t in TYPES:
            print(f"log_{t}={marked(data.splitlines(), t)}")
PY
)"

# The rule file's own ids, read in the container with the image's Python.
FILE_IDS_PY='import json, tomllib
with open("/etc/timelike/redaction.toml", "rb") as fh:
    print("file_ids=" + json.dumps(sorted(r["id"] for r in tomllib.load(fh)["rules"])))'

# The manifest's redaction_rules, read in the container.
MANIFEST_PY='import json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    rr = json.load(fh).get("redaction_rules")
rr = rr if isinstance(rr, dict) else {}
ids = rr.get("ids")
print("rules_path=" + str(rr.get("path", "<absent>")))
print("ids_count=" + (str(len(ids)) if isinstance(ids, list) else "<absent>"))
print("manifest_ids=" + (json.dumps(sorted(ids)) if isinstance(ids, list) else "<absent>"))'

setup_file() {
  stamp_check
}

setup() {
  WORK="$(container_tmpdir sc10run)"
  SESSION="sc10-${BATS_TEST_NUMBER}-${RANDOM}"
  exec_plain sh -c 'printf "%s\n" "$2" > "$1/gen.py" && printf "%s\n" "$3" > "$1/check.py"' \
    put "$WORK" "$GEN_PY" "$CHECK_PY"
  run exec_plain "$AGENT_PY" -I "${WORK}/gen.py" "$WORK"
  [[ "$status" -eq 0 ]] || { printf 'cannot generate the secrets in the container:\n%s\n' "$output" >&2; return 1; }
  assert_value generated ok
  INPUT_LINES="$(value_of input_lines)"
}

teardown() {
  container_rm "$WORK" "/tmp/timelike/${SESSION:-}"
}

# expect KEY VALUE — assert_value over the checker's output, which is in $output.
expect() { assert_value "$1" "$2"; }

# check_stored — after a run: no secret in the log the checker found (grep -cF in the container), nor
# anywhere under the test's session scratch directory (logs and events.jsonl).
check_stored() {
  local log
  log="$(value_of log)"
  [[ "$log" == "/tmp/timelike/${SESSION}/"* ]] ||
    { echo "the log is not under this test's session scratch directory: ${log}" >&2; return 1; }
  run exec_plain sh -c '
    echo "log_grep=$(grep -cF -f "$1/secrets.txt" "$2")"
    echo "session_files=$(grep -rlF -f "$1/secrets.txt" "$3" | wc -l)"
  ' grep "$WORK" "$log" "/tmp/timelike/${SESSION}"
  assert_value log_grep 0
  assert_value session_files 0
}

# check_shown_json STYLE — `run --json cat input.txt`.
check_shown_json() {
  run_in -e "TIMELIKE_SESSION=${SESSION}" "$1" notty \
    "run --json cat '${WORK}/input.txt' > '${WORK}/r.json'; rc=\$?; echo \"rc=\$rc\"; \
echo \"shown_grep=\$(grep -cF -f '${WORK}/secrets.txt' '${WORK}/r.json')\"; exit \$rc"
  assert_within 20
  assert_status 0
  assert_value rc 0
  assert_value shown_grep 0

  run exec_plain "$AGENT_PY" -I "${WORK}/check.py" json "${WORK}/r.json" "$WORK"
  [[ "$status" -eq 0 ]] || { printf 'the checker failed:\n%s\n' "$output" >&2; return 1; }
  expect json ok
  expect out_secrets 0
  expect exit 0
  expect cause command
  expect command_exit 0
  # Shown: every type's marker, and none of the secrets (out_secrets covers lines, verdict and target).
  local t n
  for t in token credential key; do
    n="$(value_of "shown_${t}")"
    at_least "$n" 1 || { printf 'no [REDACTED:%s] in the shown lines:\n%s\n' "$t" "$output" >&2; return 1; }
  done
  expect shown_lines "$INPUT_LINES"
  # Stored: the log keeps its line count (R18) and carries the markers, not the secrets.
  expect log_lines "$INPUT_LINES"
  expect log_secrets 0
  for t in token credential key; do
    n="$(value_of "log_${t}")"
    at_least "$n" 1 || { printf 'no [REDACTED:%s] in the log:\n%s\n' "$t" "$output" >&2; return 1; }
  done
  expect redaction.state applied
  expect redaction.counts '{"credential": 1, "key": 1, "token": 1}'
  expect redaction.log_rewritten true
  local verdict
  verdict="$(value_of verdict)"
  [[ "$verdict" == *" · redacted 3 (credential 1, key 1, token 1)" ]] ||
    { echo "verdict does not end ' · redacted 3 (credential 1, key 1, token 1)': ${verdict}" >&2; return 1; }
  check_stored
}

# check_shown_text STYLE — `run --text cat input.txt`.
check_shown_text() {
  run_in -e "TIMELIKE_SESSION=${SESSION}" "$1" notty \
    "run --text cat '${WORK}/input.txt' > '${WORK}/out.txt' 2> '${WORK}/err.txt'; rc=\$?; echo \"rc=\$rc\"; \
echo \"shown_grep=\$(cat '${WORK}/out.txt' '${WORK}/err.txt' | grep -cF -f '${WORK}/secrets.txt')\"; exit \$rc"
  assert_within 20
  assert_status 0
  assert_value rc 0
  assert_value shown_grep 0 # stdout and stderr alike

  run exec_plain "$AGENT_PY" -I "${WORK}/check.py" text "${WORK}/out.txt" "$WORK"
  [[ "$status" -eq 0 ]] || { printf 'the checker failed:\n%s\n' "$output" >&2; return 1; }
  expect out_secrets 0
  local header
  header="$(value_of header)"
  [[ "$header" == "run: cat ${WORK}/input.txt [run]" ]] || { echo "line 1 is not the header: ${header}" >&2; return 1; }
  local t n
  for t in token credential key; do
    n="$(value_of "shown_${t}")"
    at_least "$n" 1 || { printf 'no [REDACTED:%s] in the shown lines:\n%s\n' "$t" "$output" >&2; return 1; }
  done
  expect shown_lines "$INPUT_LINES"
  expect log_lines "$INPUT_LINES"
  expect log_secrets 0
  for t in token credential key; do
    n="$(value_of "log_${t}")"
    at_least "$n" 1 || { printf 'no [REDACTED:%s] in the log:\n%s\n' "$t" "$output" >&2; return 1; }
  done
  local verdict
  verdict="$(value_of verdict)"
  [[ "$verdict" == "exit 0 (command exited 0) · "* ]] || { echo "line 2 is not an exit-0 verdict: ${verdict}" >&2; return 1; }
  [[ "$verdict" == *" · redacted 3 (credential 1, key 1, token 1)" ]] ||
    { echo "verdict does not end ' · redacted 3 (credential 1, key 1, token 1)': ${verdict}" >&2; return 1; }
  check_stored
}

# check_header STYLE — a secret passed as an argument is redacted in the header (FR-37), in text and
# in JSON's `target`, and in what the command printed.
check_header() {
  run_in -e "TIMELIKE_SESSION=${SESSION}" "$1" notty \
    "run --text printf '%s\n' \"\$(cat '${WORK}/token.txt')\" > '${WORK}/hdr.txt'; rc=\$?; echo \"rc=\$rc\"; \
echo \"shown_grep=\$(grep -cF -f '${WORK}/token.txt' '${WORK}/hdr.txt')\"; exit \$rc"
  assert_within 20
  assert_status 0
  assert_value rc 0
  assert_value shown_grep 0

  run exec_plain "$AGENT_PY" -I "${WORK}/check.py" text "${WORK}/hdr.txt" "$WORK"
  [[ "$status" -eq 0 ]] || { printf 'the checker failed:\n%s\n' "$output" >&2; return 1; }
  expect out_secrets 0
  local header
  header="$(value_of header)"
  # shlex may or may not quote the marker; the contract fixes neither, so only the parts are asserted.
  [[ "$header" == "run: printf "* && "$header" == *"[REDACTED:token]"* && "$header" == *" [run]" ]] ||
    { echo "line 1 does not show the argument as [REDACTED:token]: ${header}" >&2; return 1; }
  local n
  n="$(value_of shown_token)"
  at_least "$n" 1 || { printf 'the printed token is not shown as [REDACTED:token]:\n%s\n' "$output" >&2; return 1; }
  expect log_secrets 0
  check_stored

  run_in -e "TIMELIKE_SESSION=${SESSION}" "$1" notty \
    "run --json printf '%s\n' \"\$(cat '${WORK}/token.txt')\" > '${WORK}/hdr.json'; rc=\$?; echo \"rc=\$rc\"; \
echo \"shown_grep=\$(grep -cF -f '${WORK}/token.txt' '${WORK}/hdr.json')\"; exit \$rc"
  assert_within 20
  assert_status 0
  assert_value shown_grep 0
  run exec_plain "$AGENT_PY" -I "${WORK}/check.py" json "${WORK}/hdr.json" "$WORK"
  [[ "$status" -eq 0 ]] || { printf 'the checker failed:\n%s\n' "$output" >&2; return 1; }
  expect json ok
  expect out_secrets 0
  local target
  target="$(value_of target)"
  [[ "$target" == "printf "* && "$target" == *"[REDACTED:token]"* ]] ||
    { echo "JSON target does not show the argument as [REDACTED:token]: ${target}" >&2; return 1; }
  check_stored
}

# check_rules STYLE — the rule file is in place and readable by the agent, and the manifest names it
# and the 18 ids, which are the file's own (FR-33, FR-40).
check_rules() {
  run_in "$1" notty \
    "if test -r /etc/timelike/redaction.toml; then echo readable=yes; else echo readable=no; fi; \
run --agent-info > '${WORK}/manifest.json'; rc=\$?; echo \"rc=\$rc\"; \
${AGENT_PY} -I -c '${FILE_IDS_PY}'; ${AGENT_PY} -I -c '${MANIFEST_PY}' '${WORK}/manifest.json'; exit \$rc"
  assert_within 20
  assert_status 0
  assert_value rc 0
  assert_value readable yes
  local want
  want="$(printf '"%s", ' "${RULE_IDS[@]}")"
  want="[${want%, }]"
  assert_value file_ids "$want"
  assert_value rules_path /etc/timelike/redaction.toml
  assert_value ids_count 18
  assert_value manifest_ids "$want"
}

@test "SC-10 values matching known secret formats are shown and stored as [REDACTED:<type>] in both the displayed output and the saved log: JSON [bash -c, notty]" { check_shown_json c; }
@test "SC-10 values matching known secret formats are shown and stored as [REDACTED:<type>] in both the displayed output and the saved log: JSON [bash -lc, notty]" { check_shown_json lc; }
@test "SC-10 values matching known secret formats are shown and stored as [REDACTED:<type>] in both the displayed output and the saved log: text [bash -c, notty]" { check_shown_text c; }
@test "SC-10 values matching known secret formats are shown and stored as [REDACTED:<type>] in both the displayed output and the saved log: text [bash -lc, notty]" { check_shown_text lc; }
@test "SC-10 a secret passed as an argument is shown as [REDACTED:token] in the header and JSON target [bash -c, notty]" { check_header c; }
@test "SC-10 a secret passed as an argument is shown as [REDACTED:token] in the header and JSON target [bash -lc, notty]" { check_header lc; }
@test "SC-10 the redaction rule file is readable and run --agent-info names it and its 18 rule ids [bash -c, notty]" { check_rules c; }
@test "SC-10 the redaction rule file is readable and run --agent-info names it and its 18 rule ids [bash -lc, notty]" { check_rules lc; }
