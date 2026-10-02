"""File discovery and running detectors over a project."""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from slopfence import diff as diffmod
from slopfence.config import is_excluded
from slopfence.detectors import FILE_DETECTORS
from slopfence.detectors.packages import PackageChecker, build_index
from slopfence.models import RULES, Finding
from slopfence.registry import Registry
from slopfence.source import SourceFile, load

EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    "__pycache__",
    "build",
    "dist",
    ".tox",
    ".nox",
    ".eggs",
    "site-packages",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


def _rel_to(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _is_dependency_file(path: Path) -> bool:
    name = path.name
    return name == "pyproject.toml" or (name.startswith("requirements") and name.endswith(".txt"))


def discover(paths: Sequence[Path]) -> tuple[list[Path], list[Path]]:
    """Return (python files, dependency files) under the given paths."""
    py_files: list[Path] = []
    dep_files: list[Path] = []
    for path in paths:
        path = path.resolve()
        if path.is_file():
            if path.suffix == ".py":
                py_files.append(path)
            elif _is_dependency_file(path):
                dep_files.append(path)
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            # Prune excluded trees (.venv, node_modules, .git...) before descending.
            dirnames[:] = [
                d for d in dirnames if d not in EXCLUDED_DIRS and not d.endswith(".egg-info")
            ]
            for filename in filenames:
                child = Path(dirpath, filename)
                if child.suffix == ".py":
                    py_files.append(child)
                elif _is_dependency_file(child):
                    dep_files.append(child)
    return sorted(set(py_files)), sorted(set(dep_files))


@dataclass
class Result:
    findings: list[Finding] = field(default_factory=list)
    files_checked: int = 0
    parse_errors: list[str] = field(default_factory=list)


def run(
    paths: Sequence[Path],
    root: Path,
    registry: Registry,
    select: Iterable[str] | None = None,
    ignore: Iterable[str] = (),
    changed: diffmod.ChangedLines | None = None,
    exclude: Sequence[str] = (),
    known_packages: Sequence[str] = (),
) -> Result:
    rules = set(select) if select else set(RULES)
    rules -= set(ignore)
    root = root.resolve()

    found_py, found_deps = discover(paths)
    # Excluded files are not checked, but still count as project modules below.
    py_files = [p for p in found_py if not is_excluded(_rel_to(p, root), exclude)]
    dep_files = [p for p in found_deps if not is_excluded(_rel_to(p, root), exclude)]
    result = Result()
    sources: list[SourceFile] = []
    for path in py_files:
        src = load(path, root)
        if src is None:
            result.parse_errors.append(_rel_to(path, root))
            continue
        sources.append(src)
    result.files_checked = len(sources) + len(dep_files)

    findings: list[Finding] = []
    for src in sources:
        for rule, detector in FILE_DETECTORS.items():
            if rule in rules:
                findings.extend(f for f in detector(src) if not src.is_ignored(f.rule, f.line))

    if "SLOP001" in rules:
        # Index the whole project, not just the checked paths: when pre-commit passes
        # only changed files, imports of the project's other modules must still resolve.
        if any(Path(p).resolve() == root for p in paths):
            all_py, all_deps = found_py, found_deps
        else:
            all_py, all_deps = discover([root])
        checker = PackageChecker(
            build_index(root, all_py, all_deps), registry, known_packages=known_packages
        )
        checked = {_rel_to(p, root) for p in dep_files}
        findings.extend(checker.check_dependencies(only_paths=checked))
        for src in sources:
            if changed is not None and src.rel not in changed:
                continue  # skip network lookups for files outside the diff
            findings.extend(
                f for f in checker.check_imports(src) if not src.is_ignored(f.rule, f.line)
            )

    if changed is not None:
        findings = [f for f in findings if diffmod.touches(changed, f.path, f.line, f.end_line)]

    result.findings = sorted(set(findings), key=lambda f: (f.path, f.line, f.col, f.rule))
    return result
