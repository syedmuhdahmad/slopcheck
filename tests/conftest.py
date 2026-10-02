from __future__ import annotations

import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest

from slopcheck.engine import Result, run
from slopcheck.registry import OfflineRegistry


class FakeRegistry:
    """Registry where only the listed packages exist."""

    def __init__(self, existing: set[str]) -> None:
        from slopcheck.registry import normalize

        self.existing = {normalize(n) for n in existing}
        self.queries: list[str] = []

    def exists(self, name: str) -> bool | None:
        from slopcheck.registry import normalize

        self.queries.append(name)
        return normalize(name) in self.existing


@pytest.fixture
def write(tmp_path: Path) -> Callable[[str, str], Path]:
    def _write(rel: str, content: str) -> Path:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content).lstrip("\n"))
        return path

    return _write


@pytest.fixture
def check(tmp_path: Path) -> Callable[..., Result]:
    def _check(*rules: str, registry=None, **kwargs) -> Result:
        return run(
            [tmp_path],
            tmp_path,
            registry or OfflineRegistry(),
            select=rules or None,
            **kwargs,
        )

    return _check


def rule_lines(result: Result, rule: str) -> list[int]:
    return [f.line for f in result.findings if f.rule == rule]
