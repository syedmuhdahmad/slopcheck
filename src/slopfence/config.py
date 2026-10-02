"""Project configuration from ``[tool.slopfence]`` in ``pyproject.toml``."""

from __future__ import annotations

import fnmatch
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from slopfence.models import RULES

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

KNOWN_KEYS = {"select", "ignore", "exclude"}


class ConfigError(ValueError):
    pass


@dataclass
class Config:
    select: list[str] | None = None
    ignore: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    path: Path | None = None


def _str_list(table: dict, key: str, where: str) -> list[str]:
    value = table[key]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{where}: '{key}' must be a list of strings")
    return value


def _rule_ids(values: list[str], key: str, where: str) -> list[str]:
    rules = [v.strip().upper() for v in values]
    unknown = [r for r in rules if r not in RULES]
    if unknown:
        raise ConfigError(f"{where}: unknown rule(s) in '{key}': {', '.join(unknown)}")
    return rules


def load_config(root: Path) -> Config:
    """Read [tool.slopfence] from root/pyproject.toml. Missing file or table -> defaults."""
    path = root / "pyproject.toml"
    if not path.is_file():
        return Config()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as err:
        raise ConfigError(f"{path}: {err}") from err
    except tomllib.TOMLDecodeError as err:
        raise ConfigError(f"{path}: invalid TOML: {err}") from err

    table = data.get("tool", {}).get("slopfence")
    if table is None:
        return Config()
    where = f"{path} [tool.slopfence]"
    if not isinstance(table, dict):
        raise ConfigError(f"{where} must be a table")
    unknown = sorted(set(table) - KNOWN_KEYS)
    if unknown:
        raise ConfigError(
            f"{where}: unknown key(s): {', '.join(unknown)} "
            f"(supported: {', '.join(sorted(KNOWN_KEYS))})"
        )

    config = Config(path=path)
    if "select" in table:
        config.select = _rule_ids(_str_list(table, "select", where), "select", where)
        if not config.select:
            raise ConfigError(f"{where}: 'select' must not be empty (omit it to run all rules)")
    if "ignore" in table:
        config.ignore = _rule_ids(_str_list(table, "ignore", where), "ignore", where)
    if "exclude" in table:
        config.exclude = _str_list(table, "exclude", where)
    return config


def is_excluded(rel_path: str, patterns: Iterable[str]) -> bool:
    """Whether a project-relative POSIX path matches any exclude pattern.

    Like .gitignore: a pattern without "/" (a trailing "/" doesn't count) matches
    any path component ("migrations", "migrations/", "*_pb2.py"). A pattern with
    "/" in the middle is anchored at the project root and matches the path or any
    of its parent directories ("tests/fixtures/", "src/gen/*.py").
    """
    parts = rel_path.split("/")
    for raw in patterns:
        pattern = raw.strip().removeprefix("./").rstrip("/")
        if not pattern:
            continue
        if "/" in pattern:
            candidates = ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]
        else:
            candidates = parts
        if any(fnmatch.fnmatchcase(c, pattern) for c in candidates):
            return True
    return False
