"""SLOP001: dependencies and imports that do not exist on PyPI.

Two checks:

* Declared dependencies (requirements*.txt, pyproject.toml) are looked up by
  their distribution name. This is the most reliable signal.
* Imports in source code are opt-in (``check-imports``), because looking them
  up sends their names to PyPI and can reveal private package names. Even then
  they are only looked up when they are not stdlib, not part of the project,
  not installed, not a declared dependency and not a well-known import name
  whose package has a different name (``yaml`` -> ``PyYAML``).
"""

from __future__ import annotations

import ast
import fnmatch
import importlib.metadata
import importlib.util
import re
import sys
import urllib.parse
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from slopfence.models import Finding
from slopfence.registry import OfflineRegistry, Registry, normalize
from slopfence.source import IGNORE_FILE_RE, IGNORE_RE, SourceFile, read_source

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
_EGG = re.compile(r"[#&]egg=([A-Za-z0-9][A-Za-z0-9._-]*)")
# pip treats "#" as a comment only at line start or after whitespace (URLs contain "#egg=").
_REQ_COMMENT = re.compile(r"(^|\s)#.*$")
_INDEX_OPTION = re.compile(r"\s*(?:-i|--index-url|--extra-index-url)(?:\s*=\s*|\s+)(\S+)")
_TABLE_HEADER = re.compile(r"^\s*\[\[?\s*([^\]]+?)\s*\]\]?\s*(#.*)?$")


@dataclass
class Dependency:
    name: str
    path: str
    line: int
    # False for packages that don't come from PyPI (URLs, paths, git, private indexes).
    validate: bool = True
    # True when an ignore directive covers SLOP001 on this line or file.
    suppressed: bool = False


@dataclass
class ProjectIndex:
    root: Path
    local_modules: set[str] = field(default_factory=set)
    dependencies: list[Dependency] = field(default_factory=list)

    @property
    def declared(self) -> set[str]:
        """Every declared name, including suppressed and non-PyPI ones."""
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


def _suppresses_slop001(line: str) -> bool:
    m = IGNORE_RE.search(line)
    if not m:
        return False
    rules = m.group("rules")
    return rules is None or "SLOP001" in {r.strip().upper() for r in rules.split(",")}


def toml_comments(text: str) -> list[str]:
    """The comment part of each line ("" if none), ignoring "#" inside TOML strings.

    Tracks multi-line strings across lines so quoted values can never carry
    a slopfence directive.
    """
    comments: list[str] = []
    multiline: str | None = None
    for line in text.split("\n"):
        comment, i = "", 0
        while i < len(line):
            if multiline:
                end = line.find(multiline, i)
                if end == -1:
                    break
                i, multiline = end + 3, None
                continue
            if line.startswith(('"""', "'''"), i):
                multiline, i = line[i : i + 3], i + 3
                continue
            ch = line[i]
            if ch in "\"'":
                j = i + 1
                while j < len(line) and line[j] != ch:
                    j += 2 if ch == '"' and line[j] == "\\" else 1
                i = j + 1
                continue
            if ch == "#":
                comment = line[i:]
                break
            i += 1
        comments.append(comment)
    return comments


def _requirements_comment(line: str) -> str:
    m = _REQ_COMMENT.search(line)
    return m.group(0) if m else ""


def parse_dependency_file(path: Path, root: Path) -> list[Dependency]:
    text = read_source(path)
    if text is None:
        return []
    rel = _rel(path, root)
    deps = (
        _parse_pyproject(text, rel)
        if path.name == "pyproject.toml"
        else _parse_requirements(text, rel)
    )
    # Directives only count inside real comments, never inside values or URLs.
    if path.name == "pyproject.toml":
        comments = toml_comments(text)
    else:
        comments = [_requirements_comment(line) for line in text.splitlines()]
    if any(IGNORE_FILE_RE.search(c) for c in comments):
        for dep in deps:
            dep.suppressed = True
    return deps


def _parse_requirements(text: str, rel: str) -> list[Dependency]:
    lines = text.splitlines()
    # With a non-PyPI index, a name missing from PyPI may be a private package.
    private_index = any(
        (m := _INDEX_OPTION.match(_REQ_COMMENT.sub("", line))) and not _is_public_index(m.group(1))
        for line in lines
    )
    deps = []
    for lineno, raw in enumerate(lines, start=1):
        suppressed = _suppresses_slop001(_requirements_comment(raw))
        line = _REQ_COMMENT.sub("", raw).strip()
        if not line:
            continue
        if line.startswith(
            ("-", "git+", "hg+", "svn+", "bzr+", "http:", "https:", "file:", ".", "/")
        ):
            # Options and bare URLs/paths: the name is only known from #egg=.
            if m := _EGG.search(line):
                deps.append(
                    Dependency(m.group(1), rel, lineno, validate=False, suppressed=suppressed)
                )
            continue
        if m := _REQ_NAME.match(line):
            direct_url = "@" in line and "://" in line  # name @ https://...
            deps.append(
                Dependency(
                    m.group(1),
                    rel,
                    lineno,
                    validate=not (direct_url or private_index),
                    suppressed=suppressed,
                )
            )
    return deps


def _table_ranges(lines: list[str]) -> dict[str, tuple[int, int]]:
    """Map each TOML table header to its (first, last) 0-based line range."""
    headers = [(i, m.group(1)) for i, line in enumerate(lines) if (m := _TABLE_HEADER.match(line))]
    ranges = {}
    for n, (start, name) in enumerate(headers):
        end = headers[n + 1][0] - 1 if n + 1 < len(headers) else len(lines) - 1
        ranges.setdefault(name.replace(" ", ""), (start, end))
    return ranges


class _LineFinder:
    """Find the physical line of each dependency entry within its own TOML table."""

    def __init__(self, text: str) -> None:
        self.lines = text.splitlines()
        self.comments = toml_comments(text)
        self.ranges = _table_ranges(self.lines)
        # (line, column) of entries already matched, so repeated specs map to
        # successive occurrences and several entries can share one line.
        self.used: set[tuple[int, int]] = set()

    def _array_range(self, start: int, end: int, key: str) -> tuple[int, int] | None:
        """Lines spanned by `key = [ ... ]` inside a table, using quote-aware bracket counting."""
        key_re = re.compile(r"""^\s*["']?""" + re.escape(key) + r"""["']?\s*=""")
        for i in range(start, end + 1):
            if not key_re.match(self.lines[i]):
                continue
            depth, seen_open = 0, False
            for j in range(i, end + 1):
                quote: str | None = None
                for ch in self.lines[j]:
                    if quote:
                        if ch == quote:
                            quote = None
                    elif ch in "\"'":
                        quote = ch
                    elif ch == "#":
                        break
                    elif ch == "[":
                        depth, seen_open = depth + 1, True
                    elif ch == "]":
                        depth -= 1
                if seen_open and depth <= 0:
                    return i, j
            return i, end
        return None

    def _search(self, table: str, pattern: re.Pattern[str], array: str | None = None) -> int:
        start, end = self.ranges.get(table, (0, len(self.lines) - 1))
        if array is not None and (span := self._array_range(start, end, array)):
            start, end = span
        for i in range(start, end + 1):
            line = self.lines[i]
            if line.lstrip().startswith("#"):  # commented-out entries
                continue
            for m in pattern.finditer(line):
                if (i, m.start()) not in self.used:
                    self.used.add((i, m.start()))
                    return i + 1
        return start + 1

    def spec(self, table: str, array: str, spec: str) -> int:
        quoted = re.compile(r"""(["'])""" + re.escape(spec) + r"\1")
        return self._search(table, quoted, array)

    def key(self, table: str, name: str) -> int:
        return self._search(
            table, re.compile(r"""^\s*["']?""" + re.escape(name) + r"""["']?\s*=""")
        )

    def suppressed(self, line: int) -> bool:
        return 0 < line <= len(self.comments) and _suppresses_slop001(self.comments[line - 1])


PUBLIC_INDEX_HOSTS = ("pypi.org", "pythonhosted.org")


def _is_public_index(url: object) -> bool:
    """Whether an index URL points at PyPI itself (by host, not substring)."""
    if not isinstance(url, str):
        return False
    try:
        host = (urllib.parse.urlsplit(url.strip()).hostname or "").lower()
    except ValueError:
        return False
    return any(host == h or host.endswith("." + h) for h in PUBLIC_INDEX_HOSTS)


def _uses_private_index(tool: dict) -> bool:
    """Whether Poetry or uv may install any dependency from a non-PyPI index.

    Then a name that's missing from PyPI may be a private package, so it must
    neither be reported nor sent to PyPI.
    """
    poetry_sources = tool.get("poetry", {}).get("source", [])
    for source in poetry_sources if isinstance(poetry_sources, list) else []:
        # Only "explicit" sources are limited to dependencies that name them (handled
        # per dependency); primary, supplemental and the legacy kinds serve any package.
        if (
            isinstance(source, dict)
            and source.get("priority") != "explicit"
            and not _is_public_index(source.get("url"))
        ):
            return True
    uv = tool.get("uv", {})
    indexes = uv.get("index", [])
    for index in indexes if isinstance(indexes, list) else []:
        if (
            isinstance(index, dict)
            and not index.get("explicit")
            and not _is_public_index(index.get("url"))
        ):
            return True
    extra = uv.get("extra-index-url", [])
    urls = [uv.get("index-url"), *(extra if isinstance(extra, list) else [extra])]
    return any(url is not None and not _is_public_index(url) for url in urls)


def _parse_pyproject(text: str, rel: str) -> list[Dependency]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []
    finder = _LineFinder(text)
    deps: list[Dependency] = []
    project = data.get("project", {})
    project_name = normalize(project["name"]) if isinstance(project.get("name"), str) else None
    tool = data.get("tool", {})
    uv_sources = {normalize(n) for n in tool.get("uv", {}).get("sources", {})}
    private_index = _uses_private_index(tool)

    def add_spec(table: str, array: str, spec: object) -> None:
        if not isinstance(spec, str) or not (m := _REQ_NAME.match(spec)):
            return
        name = m.group(1)
        if normalize(name) == project_name:  # self-references like "pkg[extra]"
            return
        line = finder.spec(table, array, spec)
        validate = not private_index and "://" not in spec and normalize(name) not in uv_sources
        deps.append(Dependency(name, rel, line, validate, finder.suppressed(line)))

    for spec in project.get("dependencies", []):
        add_spec("project", "dependencies", spec)
    optional_table = (
        "project.optional-dependencies"
        if "project.optional-dependencies" in finder.ranges
        else "project"
    )
    for group, specs in project.get("optional-dependencies", {}).items():
        array = group if optional_table != "project" else "optional-dependencies"
        for spec in specs:
            add_spec(optional_table, array, spec)
    for group, specs in data.get("dependency-groups", {}).items():
        for spec in specs:
            add_spec("dependency-groups", group, spec)

    poetry = tool.get("poetry", {})
    tables = {
        "tool.poetry.dependencies": poetry.get("dependencies", {}),
        "tool.poetry.dev-dependencies": poetry.get("dev-dependencies", {}),
    }
    for group, body in poetry.get("group", {}).items():
        tables[f"tool.poetry.group.{group}.dependencies"] = body.get("dependencies", {})
    for table, entries in tables.items():
        for name, spec in entries.items():
            if name.lower() == "python":
                continue
            specs = spec if isinstance(spec, list) else [spec]
            external = any(
                isinstance(s, dict) and {"path", "git", "url", "source"} & set(s) for s in specs
            )
            line = finder.key(table, name)
            validate = not (external or private_index)
            deps.append(Dependency(name, rel, line, validate, finder.suppressed(line)))
    return deps


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
    def __init__(
        self, index: ProjectIndex, registry: Registry, known_packages: Iterable[str] = ()
    ) -> None:
        self.index = index
        self.registry = registry
        # Private/internal packages the user vouches for; globs allowed ("corp-*").
        self._known = [normalize(p) for p in known_packages]
        self._installed = _installed_modules()
        self._declared = index.declared
        self._missing: dict[str, bool] = {}

    def check_dependencies(self, only_paths: set[str] | None = None) -> Iterator[Finding]:
        for dep in self.index.dependencies:
            if only_paths is not None and dep.path not in only_paths:
                continue
            if not dep.validate or dep.suppressed or self._is_known(dep.name):
                continue
            if self.registry.exists(dep.name) is False:
                yield Finding(
                    "SLOP001",
                    dep.path,
                    dep.line,
                    1,
                    f"Dependency '{dep.name}' does not exist on PyPI (possible hallucination)",
                )

    def _is_known(self, name: str) -> bool:
        key = normalize(name)
        return any(fnmatch.fnmatchcase(key, pattern) for pattern in self._known)

    def _should_lookup(self, name: str) -> bool:
        return not (
            self._is_known(name)
            or name in sys.stdlib_module_names
            or name == "__future__"
            or name in sys.builtin_module_names
            or name in self.index.local_modules
            or name in KNOWN_IMPORT_NAMES
            or normalize(name) in self._declared
            or _is_installed(name, self._installed)
        )

    def _is_missing(self, name: str) -> bool:
        """Cached per name; every import occurrence is still reported separately."""
        if name not in self._missing:
            missing = False
            if self._should_lookup(name):
                answers = [self.registry.exists(c) for c in {name, name.replace("_", "-")}]
                missing = all(a is False for a in answers)
            self._missing[name] = missing
        return self._missing[name]

    def check_imports(self, src: SourceFile) -> Iterator[Finding]:
        if isinstance(self.registry, OfflineRegistry):
            return
        for name, node in _top_level_imports(src.tree):
            if self._is_missing(name):
                yield Finding(
                    "SLOP001",
                    src.rel,
                    node.lineno,
                    node.col_offset + 1,
                    f"Import '{name}' is not installed, not declared, and no package with "
                    "that name exists on PyPI (possible hallucination)",
                )
