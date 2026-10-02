"""Restrict findings to lines changed relative to a git ref."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

# path (relative to repo root) -> changed line numbers; None means the whole file is new.
ChangedLines = dict[str, "set[int] | None"]


class DiffError(RuntimeError):
    pass


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=True
        )
    except FileNotFoundError as err:
        raise DiffError("git is not installed") from err
    except subprocess.CalledProcessError as err:
        raise DiffError(err.stderr.strip() or f"git {' '.join(args)} failed") from err
    return result.stdout


def repo_root(start: Path) -> Path | None:
    try:
        return Path(_git(start, "rev-parse", "--show-toplevel").strip())
    except DiffError:
        return None


def parse_unified_diff(diff_text: str) -> ChangedLines:
    changed: ChangedLines = {}
    current: str | None = None
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            current = None if target == "/dev/null" else target.removeprefix("b/")
            if current is not None:
                changed.setdefault(current, set())
        elif current is not None and (m := _HUNK.match(line)):
            start = int(m.group(1))
            count = int(m.group(2)) if m.group(2) is not None else 1
            lines = changed[current]
            assert lines is not None
            lines.update(range(start, start + count))
    return changed


def changed_lines(root: Path, ref: str) -> ChangedLines:
    """Lines changed between merge-base(ref, HEAD) and the working tree, plus untracked files."""
    base = _git(root, "merge-base", ref, "HEAD").strip()
    diff = _git(root, "diff", "--unified=0", "--no-color", "--no-ext-diff", base)
    changed = parse_unified_diff(diff)
    for path in _git(root, "ls-files", "--others", "--exclude-standard").splitlines():
        changed[path] = None
    return changed


def touches(changed: ChangedLines, path: str, line: int, end_line: int | None) -> bool:
    if path not in changed:
        return False
    lines = changed[path]
    if lines is None:
        return True
    return any(n in lines for n in range(line, (end_line or line) + 1))
