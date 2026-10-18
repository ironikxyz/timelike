"""The build on a host whose disk is the limit (feedback 13-20261018-030300).

Lanes 13s0c and 13s0d stopped at `make build`: uv's bytecode compile of the standard library timed out at its
60 s default while one `compose build` built every image at once on a saturated disk. Two levers, both read
here from the files themselves: the Makefile builds the compose images one after another, and every
`--compile-bytecode` carries a 300 s bound, refused at build time by a uv that does not read it. The agent
image's second compile waits for its first through a bind mount of the runtimes stage.
"""

from __future__ import annotations

import re

import pytest
from conftest import REPO

DOCKERFILES = ("image/Dockerfile", "bench/vanilla/Dockerfile", "bench/driver/Dockerfile")


def build_services_in_compose() -> list[str]:
    text = (REPO / "compose.yaml").read_text()
    services = text[text.index("\nservices:\n") + len("\nservices:\n") :]
    end = re.search(r"^\S", services, re.MULTILINE)
    services = services[: end.start()] if end else services
    out = []
    for m in re.finditer(r"^  ([a-z][a-z0-9-]*):\n((?:    .*\n|\s*\n)*)", services, re.MULTILINE):
        if re.search(r"^    build:", m.group(2), re.MULTILINE):
            out.append(m.group(1))
    return out


def test_the_makefile_builds_every_compose_image_one_at_a_time() -> None:
    text = (REPO / "Makefile").read_text()
    m = re.search(r"^BUILD_SERVICES := (.*)$", text, re.MULTILINE)
    assert m, "the Makefile has no BUILD_SERVICES"
    listed = m.group(1).split()
    assert sorted(listed) == sorted(build_services_in_compose()), (
        f"BUILD_SERVICES {listed} is not compose.yaml's services with a build section"
        f" {build_services_in_compose()}"
    )
    assert listed.index("adele") < listed.index("adele-standin"), (
        "adele-standin must follow adele (shared Go stage)"
    )
    recipe = re.search(r"^build:.*\n((?:\t.*\n?)+)", text, re.MULTILINE).group(1)
    assert "for s in $(BUILD_SERVICES)" in recipe, "build does not loop over BUILD_SERVICES"
    assert re.search(r"build --build-arg GIT_SHA=\$\(GIT_SHA\) \"\$\$s\"", recipe), (
        "build does not build one service"
    )


def compile_runs(path: str) -> list[str]:
    runs = re.split(r"^RUN ", (REPO / path).read_text(), flags=re.MULTILINE)[1:]
    return [r for r in runs if "--compile-bytecode" in r]


@pytest.mark.parametrize("path", DOCKERFILES)
def test_every_bytecode_compile_has_the_raised_bound_and_its_guard(path: str) -> None:
    runs = compile_runs(path)
    assert runs, f"{path} has no --compile-bytecode step"
    for run in runs:
        assert "UV_COMPILE_BYTECODE_TIMEOUT=300 " in run, f"a compile in {path} keeps uv's 60 s default"
        guard = run.index("grep -qaF UV_COMPILE_BYTECODE_TIMEOUT /bin/uv")
        assert guard < run.index("uv python install"), f"{path}: the guard must run before the install"


def test_the_agent_images_second_compile_waits_for_its_first() -> None:
    text = (REPO / "image/Dockerfile").read_text()
    final = text[text.index("\nFROM ${DEBIAN_IMAGE}\n") :]
    (run,) = compile_runs("image/Dockerfile")[1:]
    assert run in final, "the second compile is not in the final stage"
    assert run.startswith("--mount=type=bind,from=runtimes,"), (
        "the final stage's compile does not wait for runtimes"
    )
