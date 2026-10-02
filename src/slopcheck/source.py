"""Parsed view of a Python file: AST, comments, docstrings and ignore directives."""

from __future__ import annotations

import ast
import io
import re
import tokenize
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

_IGNORE_RE = re.compile(r"#\s*slopcheck:\s*ignore(?:\[(?P<rules>[A-Z0-9,\s]+)\])?(?!-)", re.I)
_IGNORE_FILE_RE = re.compile(r"#\s*slopcheck:\s*ignore-file\b", re.I)


@dataclass
class TextSpan:
    """A line of comment or docstring text with its location (1-based line and column)."""

    line: int
    col: int
    text: str


@dataclass
class SourceFile:
    path: Path
    rel: str
    text: str
    tree: ast.Module
    comments: list[TextSpan] = field(default_factory=list)
    # line -> rule IDs to ignore on that line; None means every rule.
    ignores: dict[int, set[str] | None] = field(default_factory=dict)
    ignore_file: bool = False

    @property
    def is_test_file(self) -> bool:
        name = self.path.name
        return (
            name.startswith("test_")
            or name.endswith("_test.py")
            or name == "conftest.py"
            # Relative parts, so a project that lives under ~/tests/ isn't all "test code".
            or bool({"tests", "test"} & set(Path(self.rel).parts[:-1]))
        )

    def is_ignored(self, rule: str, line: int) -> bool:
        if self.ignore_file:
            return True
        if line not in self.ignores:
            return False
        rules = self.ignores[line]
        return rules is None or rule in rules

    @cached_property
    def docstring_lines(self) -> list[TextSpan]:
        """Each line of every module, class and function docstring."""
        return list(self._iter_docstring_lines())

    def _iter_docstring_lines(self) -> Iterator[TextSpan]:
        nodes = [self.tree] + [
            n
            for n in ast.walk(self.tree)
            if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for node in nodes:
            body = node.body
            if not (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                continue
            const = body[0].value
            for offset, text in enumerate(const.value.splitlines()):
                if text.strip():
                    yield TextSpan(const.lineno + offset, const.col_offset + 1, text)

    def text_spans(self) -> Iterator[TextSpan]:
        """Comments and docstring lines: where AI chat text and placeholders hide."""
        yield from self.comments
        yield from self.docstring_lines


def load(path: Path, root: Path) -> SourceFile | None:
    """Parse a file. Returns None if it is not valid Python."""
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError):
        return None

    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = path.as_posix()

    src = SourceFile(path=path, rel=rel, text=text, tree=tree)
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type != tokenize.COMMENT:
                continue
            line, col = tok.start
            src.comments.append(TextSpan(line, col + 1, tok.string))
            if _IGNORE_FILE_RE.search(tok.string):
                src.ignore_file = True
            elif m := _IGNORE_RE.search(tok.string):
                rules = m.group("rules")
                src.ignores[line] = (
                    {r.strip().upper() for r in rules.split(",") if r.strip()} if rules else None
                )
    except (tokenize.TokenError, IndentationError):
        pass
    return src
