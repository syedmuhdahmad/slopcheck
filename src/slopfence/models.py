from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def rank(self) -> int:
        return {"low": 1, "medium": 2, "high": 3}[self.value]


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    severity: Severity
    summary: str


RULES: dict[str, Rule] = {
    rule.id: rule
    for rule in [
        Rule(
            "SLOP001",
            "nonexistent-package",
            Severity.HIGH,
            "Dependency or import that does not exist on PyPI (possible hallucination).",
        ),
        Rule(
            "SLOP010",
            "placeholder-comment",
            Severity.MEDIUM,
            "Placeholder or stub comment left in code that looks finished.",
        ),
        Rule(
            "SLOP020",
            "test-asserts-only-mocks",
            Severity.HIGH,
            "Test only asserts on mocks it created itself and never calls real code.",
        ),
        Rule(
            "SLOP021",
            "test-trivial-assertion",
            Severity.MEDIUM,
            "Test whose only assertions are always true (e.g. `assert True`).",
        ),
        Rule(
            "SLOP022",
            "test-cannot-fail",
            Severity.HIGH,
            "Test assertions are wrapped in try/except that swallows the failure.",
        ),
        Rule(
            "SLOP051",
            "chat-leftover",
            Severity.MEDIUM,
            "Leftover AI chat text in a comment or docstring.",
        ),
    ]
}


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int
    col: int
    message: str
    # Last line of the flagged construct, used by --diff to match changed functions.
    end_line: int | None = None

    @property
    def severity(self) -> Severity:
        return RULES[self.rule].severity
