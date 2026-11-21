"""Hook tests run with the kit's hooks enabled.

`HIWAY_KIT_DISABLE_HOOKS` reaches every process a Claude Code session starts (it is set through
settings `env`), including a contributor's `verify-done.sh`. If it leaked into these tests, "must
block" cases would fail and "must pass" cases would pass without checking anything.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _hooks_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HIWAY_KIT_DISABLE_HOOKS", raising=False)
