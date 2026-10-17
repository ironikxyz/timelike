"""The state root in the build files (feature 005 slice 1, T027; spec FR-25, FR-26; rule 10 at revision 11).

Static checks, as test_agent_runtimes.py does them (its helpers are reused): the image creates
/var/lib/timelike owned by agent, mode 0700, before any volume is mounted there (lore docker-compose
Q003); the ENV names it; compose mounts the named volume timelike-state there on the agent service only,
and nothing else; the vanilla image gets none of it (P6, bench parity). What a built container does is the
e2e cells' (state-root-*.bats and the SC-8 recreate cell).
"""

from __future__ import annotations

import re

from test_agent_runtimes import AGENT_DOCKERFILE, COMPOSE, VANILLA_DOCKERFILE, instructions, read


def _agent_block() -> str:
    m = re.search(r"^  agent:\n((?:    .*\n|\s*\n)+)", read(COMPOSE), re.MULTILINE)
    assert m, "compose.yaml has no agent service"
    return m.group(1)


def test_the_image_creates_the_state_root_owned_by_agent_0700() -> None:
    runs = [i for i in instructions(AGENT_DOCKERFILE) if i.startswith("RUN ")]
    users = [r for r in runs if "useradd --uid 1000" in r]
    assert len(users) == 1, "one RUN creates the agent user"
    assert re.search(r"install -d -o agent -g agent -m 0700 /var/lib/timelike\b", users[0])
    assert 'test "$(stat -c \'%a %U:%G\' /var/lib/timelike)" = "700 agent:agent"' in users[0]


def test_the_env_names_the_state_root_and_nothing_writes_it_at_build() -> None:
    envs = " ".join(i for i in instructions(AGENT_DOCKERFILE) if i.startswith("ENV "))
    assert 'TIMELIKE_STATE_ROOT="/var/lib/timelike"' in envs
    announce = [i for i in instructions(AGENT_DOCKERFILE) if "announce --write" in i]
    assert announce and 'test -z "$(ls -A /var/lib/timelike)"' in announce[0]  # no root-owned VERSION


def test_compose_mounts_only_timelike_state_on_the_agent() -> None:
    block = _agent_block()
    v = re.search(r"^    volumes:\n((?:      - .*\n)+)", block, re.MULTILINE)
    assert v, "the agent service mounts its state root"
    # Feature 13 adds the workspace, a host directory at the same absolute path (014 research R9), with an
    # empty named volume when none was set; nothing else, and nothing of Adele's.
    assert [x.strip() for x in v.group(1).strip().splitlines()] == [
        "- timelike-state:/var/lib/timelike",
        "- ${TIMELIKE_WORKSPACE:-timelike-no-workspace}:${TIMELIKE_WORKSPACE:-/opt/timelike/no-workspace}",
    ]
    assert "docker.sock" not in block and "adele" not in v.group(1)
    top = re.search(r"^volumes:\n((?:  \S.*\n)+)", read(COMPOSE), re.MULTILINE)
    assert top and re.search(r"^  timelike-state:\s*$", top.group(1), re.MULTILINE)


def test_no_other_service_mounts_timelike_state() -> None:
    text = read(COMPOSE)
    assert text.count("timelike-state:/var/lib/timelike") == 1


def test_vanilla_gets_no_state_root() -> None:
    text = read(VANILLA_DOCKERFILE)
    assert "/var/lib/timelike" not in text and "TIMELIKE_STATE_ROOT" not in text


def test_the_helpers_ship_executable_beside_the_tools() -> None:
    copies = [i for i in instructions(AGENT_DOCKERFILE) if i.startswith("COPY ") and "tools/libexec/" in i]
    assert copies and "--chmod=0755" in copies[0] and copies[0].rstrip().endswith("/opt/timelike/libexec/")
