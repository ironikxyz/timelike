"""`tools/bin/package-guard` loaded as a module, for the units of its pure functions (feature 013)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

PATH = Path(__file__).resolve().parents[2] / "tools" / "bin" / "package-guard"
NAME = "timelike_package_guard_under_test"


def load() -> ModuleType:
    if NAME in sys.modules:
        return sys.modules[NAME]
    loader = importlib.machinery.SourceFileLoader(NAME, str(PATH))
    spec = importlib.util.spec_from_loader(NAME, loader)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[NAME] = mod  # dataclasses look their module up while the class is built
    loader.exec_module(mod)
    return mod


PG = load()
