"""SLOP001: dependencies and imports that do not exist on PyPI.

Two checks:

* Declared dependencies (requirements*.txt, pyproject.toml) are looked up by
  their distribution name. This is the most reliable signal.
* Imports are only looked up when they are not stdlib, not part of the
  project, not installed, not a declared dependency and not a well-known
  import name whose package has a different name (``yaml`` -> ``PyYAML``).
"""

from __future__ import annotations

import ast
import importlib.metadata
import importlib.util
import re
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from slopcheck.models import Finding
from slopcheck.registry import OfflineRegistry, Registry, normalize
from slopcheck.source import SourceFile

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

# Import names whose PyPI distribution is named differently.
KNOWN_IMPORT_NAMES = {
    "attr",
    "bs4",
    "cv2",
    "Crypto",
    "Cryptodome",
    "dateutil",
    "docx",
    "dotenv",
    "fitz",
    "gi",
    "git",
    "google",
    "jose",
    "jwt",
    "Levenshtein",
    "magic",
    "multipart",
    "MySQLdb",
    "OpenSSL",
    "PIL",
    "pkg_resources",
    "pptx",
    "psycopg2",
    "pydantic_core",
    "serial",
    "skimage",
    "sklearn",
    "slugify",
    "socketio",
    "telegram",
    "usb",
    "win32api",
    "win32con",
    "win32com",
    "pythoncom",
    "pywintypes",
    "wx",
    "yaml",
    "zmq",
    "_pytest",
    "pytest",
    "setuptools",
    "distutils",
    "typing_extensions",
    "six",
    "grpc",
    "Bio",
    "ldap",
    "nacl",
    "OpenGL",
    "sentry_sdk",
    "rest_framework",
    "jinja2",
    "markdown",
    "lxml",
    "xdist",
    "faiss",
    "torch",
    "torchvision",
    "tensorflow",
    "keras",
}

_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


@dataclass
class Dependency:
    name: str
    path: str
    line: int


@dataclass
class ProjectIndex:
    root: Path
    local_modules: set[str] = field(default_factory=set)
    dependencies: list[Dependency] = field(default_factory=list)

    @property
    def declared(self) -> set[str]:
        return {normalize(d.name) for d in self.dependencies}


def build_index(root: Path, py_files: Iterable[Path], dep_files: Iterable[Path]) -> ProjectIndex:
    index = ProjectIndex(root=root)
    for path in py_files:
        index.local_modules.add(path.stem)
        for parent in path.parents:
            if parent == root or root not in parent.parents:
                break
            index.local_modules.add(parent.name)
    for path in dep_files:
        index.dependencies.extend(parse_dependency_file(path, root))
    return index


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def parse_dependency_file(path: Path, root: Path) -> list[Dependency]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    rel = _rel(path, root)
    if path.name == "pyproject.toml":
        return _parse_pyproject(text, rel)
    deps = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if "slopcheck: ignore" in raw:
            continue
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "git+", "http:", "https:", "file:", ".", "/")):
            continue
        if "@" in line and "://" in line:  # name @ https://... direct references
            continue
        if m := _REQ_NAME.match(line):
            deps.append(Dependency(m.group(1), rel, lineno))
    return deps


def _parse_pyproject(text: str, rel: str) -> list[Dependency]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []
    specs: list[str] = []
    project = data.get("project", {})
    specs += project.get("dependencies", [])
    for group in project.get("optional-dependencies", {}).values():
        specs += group
    for group in data.get("dependency-groups", {}).values():
        specs += [s for s in group if isinstance(s, str)]
    poetry = data.get("tool", {}).get("poetry", {})
    poetry_names = [
        name
        for table in [poetry.get("dependencies", {}), poetry.get("dev-dependencies", {})]
        + [g.get("dependencies", {}) for g in poetry.get("group", {}).values()]
        for name, spec in table.items()
        if name.lower() != "python"
        and not (isinstance(spec, dict) and ("path" in spec or "git" in spec))
    ]
    project_name = normalize(project.get("name", "")) if project.get("name") else None

    lines = text.splitlines()
    deps = []
    for spec in specs:
        if "://" in spec:
            continue
        if m := _REQ_NAME.match(spec):
            name = m.group(1)
            if normalize(name) != project_name:  # self-references like "pkg[extra]"
                deps.append(Dependency(name, rel, _find_line(lines, spec)))
    for name in poetry_names:
        deps.append(Dependency(name, rel, _find_line(lines, name)))
    return deps


def _find_line(lines: list[str], needle: str) -> int:
    for i, line in enumerate(lines, start=1):
        if needle in line:
            return i
    return 1


def _installed_modules() -> set[str]:
    try:
        return set(importlib.metadata.packages_distributions())
    except Exception:  # pragma: no cover - broken environments
        return set()


def _top_level_imports(tree: ast.Module) -> Iterator[tuple[str, ast.stmt]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0], node
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0], node


def _is_installed(name: str, installed: set[str]) -> bool:
    if name in installed:
        return True
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


class PackageChecker:
    def __init__(self, index: ProjectIndex, registry: Registry) -> None:
        self.index = index
        self.registry = registry
        self._installed = _installed_modules()
        self._declared = index.declared

    def check_dependencies(self, only_paths: set[str] | None = None) -> Iterator[Finding]:
        for dep in self.index.dependencies:
            if only_paths is not None and dep.path not in only_paths:
                continue
            if self.registry.exists(dep.name) is False:
                yield Finding(
                    "SLOP001",
                    dep.path,
                    dep.line,
                    1,
                    f"Dependency '{dep.name}' does not exist on PyPI (possible hallucination)",
                )

    def _should_lookup(self, name: str) -> bool:
        return not (
            name in sys.stdlib_module_names
            or name == "__future__"
            or name in sys.builtin_module_names
            or name in self.index.local_modules
            or name in KNOWN_IMPORT_NAMES
            or normalize(name) in self._declared
            or _is_installed(name, self._installed)
        )

    def check_imports(self, src: SourceFile) -> Iterator[Finding]:
        if isinstance(self.registry, OfflineRegistry):
            return
        seen: set[str] = set()
        for name, node in _top_level_imports(src.tree):
            if name in seen or not self._should_lookup(name):
                continue
            seen.add(name)
            candidates = {name, name.replace("_", "-")}
            answers = [self.registry.exists(c) for c in candidates]
            if answers and all(a is False for a in answers):
                yield Finding(
                    "SLOP001",
                    src.rel,
                    node.lineno,
                    node.col_offset + 1,
                    f"Import '{name}' is not installed, not declared, and no package with "
                    "that name exists on PyPI (possible hallucination)",
                )
