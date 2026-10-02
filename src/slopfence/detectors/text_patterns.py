"""SLOP010 (placeholder comments) and SLOP051 (chat leftovers).

Both scan only comments and docstrings, never string literals, so user-facing
messages like "Sure!" in a UI string are not flagged.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from slopfence.models import Finding
from slopfence.source import SourceFile

PLACEHOLDER_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"\bin an? (real|production|full|actual|complete|proper)[- ]"
        r"(implementation|app|application|system|world|scenario|environment|project|code)",
        r"\b(simplified|simple|basic|dummy|mock) (implementation|version|logic) "
        r"(for|to) (demo|demonstration|illustration|example|brevity|now)",
        r"\bfor (demo|demonstration|illustration|example) purposes\b",
        r"\b(placeholder|stub) (implementation|logic|code)\b",
        r"\b(replace|swap) (this|it) with (your|the|an?) (actual|real|own)\b",
        r"\byour (actual |own )?(logic|code|implementation|api[ _-]?key) (goes )?here\b",
        r"\.\.\.\s*(rest of|remaining|existing|other) (the )?(code|implementation|logic)\b",
        r"\bthis is (just )?a (placeholder|simplified) (implementation|version|function)\b",
        r"\badd (your|more|actual|real) (logic|implementation|validation|error handling) here\b",
    ]
]

CHAT_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        # Chat openers: "Certainly!", "Sure, here is..." (not prose like "Of course, you can...").
        r"^\W*(certainly|sure|absolutely|of course)\s*!",
        r"^\W*(certainly|sure|absolutely|of course)[,.]?\s+(here|below|i'll|i will|let me)\b",
        r"\bhere(?:'s| is) (the|an?|your) (updated|revised|modified|corrected|complete|"
        r"refactored|fixed|improved|final) (version|code|function|implementation|script|"
        r"file|class|method|snippet|module)\b",
        r"\bbelow is (the|an?) (updated|revised|complete|full|modified|corrected) "
        r"(version|code|function|implementation|script|file|class|method|snippet|module)\b",
        r"\bas an ai( language model)?\b",
        r"\bi hope (this|that) helps\b",
        r"\blet me know if (you('d| would) like|you need|you have any (other |more |further )?"
        r"questions|there('s| is) anything else|you want)\b",
        r"\bgreat question\b",
        r"\bhappy to help\b",
        r"\bi apologi[sz]e for (the|any) (confusion|error|mistake|oversight)\b",
    ]
]


def _scan(
    src: SourceFile, rule: str, patterns: list[re.Pattern[str]], label: str
) -> Iterator[Finding]:
    for span in src.text_spans():
        text = span.text.lstrip("#").strip().strip("\"'").strip()
        for pattern in patterns:
            if pattern.search(text):
                snippet = text if len(text) <= 80 else text[:77] + "..."
                yield Finding(rule, src.rel, span.line, span.col, f'{label}: "{snippet}"')
                break


def check_placeholders(src: SourceFile) -> Iterator[Finding]:
    # Test code often describes production behaviour on purpose; only check app code.
    if src.is_test_file:
        return
    yield from _scan(src, "SLOP010", PLACEHOLDER_PATTERNS, "Placeholder left in code")


def check_chat_leftovers(src: SourceFile) -> Iterator[Finding]:
    yield from _scan(src, "SLOP051", CHAT_PATTERNS, "Leftover AI chat text")
