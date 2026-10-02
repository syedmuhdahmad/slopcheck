"""Private package indexes: when a name missing from PyPI may still be a real package.

If pip, uv, Poetry, PDM or Pipenv may install packages from an index other than
PyPI, a dependency or import that PyPI doesn't know could be a private package.
Such names must neither be reported as hallucinations nor sent to PyPI.

Index URLs are only compared by host and are never printed: they can contain
credentials.
"""

from __future__ import annotations

import configparser
import os
import sys
import urllib.parse
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

PUBLIC_INDEX_HOSTS = ("pypi.org", "pythonhosted.org")


def is_public_index(url: object) -> bool:
    """Whether an index URL points at PyPI itself (by host, not substring)."""
    if not isinstance(url, str):
        return False
    try:
        host = (urllib.parse.urlsplit(url.strip()).hostname or "").lower()
    except ValueError:
        return False
    return any(host == h or host.endswith("." + h) for h in PUBLIC_INDEX_HOSTS)


def _private(urls: Iterable[object]) -> bool:
    """Whether any of the given index URLs is set and isn't PyPI."""
    return any(url is not None and not is_public_index(url) for url in urls)


def _list(value: object) -> list:
    """A TOML value that may be a single item or a list, as a list."""
    if isinstance(value, list):
        return value
    return [] if value is None else [value]


def uses_private_index(tool: Mapping) -> bool:
    """Whether a pyproject.toml ``[tool]`` table lets any dependency come from a
    non-PyPI index (Poetry, uv or PDM)."""
    poetry = tool.get("poetry", {})
    for source in _list(poetry.get("source") if isinstance(poetry, dict) else None):
        # Only "explicit" sources are limited to dependencies that name them (handled
        # per dependency); primary, supplemental and the legacy kinds serve any package.
        if (
            isinstance(source, dict)
            and source.get("priority") != "explicit"
            and _private([source.get("url")])
        ):
            return True
    uv = tool.get("uv", {})
    if isinstance(uv, dict) and uv_config_is_private(uv):
        return True
    pdm = tool.get("pdm", {})
    for source in _list(pdm.get("source") if isinstance(pdm, dict) else None):
        # PDM's "find_links" sources hold files, not an index, but serve packages too.
        if isinstance(source, dict) and _private([source.get("url")]):
            return True
    return False


def uv_config_is_private(uv: Mapping) -> bool:
    """Whether uv settings (``[tool.uv]`` or a ``uv.toml``) use a non-PyPI index."""
    for index in _list(uv.get("index")):
        if isinstance(index, dict) and not index.get("explicit") and _private([index.get("url")]):
            return True
    return _private([uv.get("index-url"), *_list(uv.get("extra-index-url"))])


def pipfile_is_private(data: Mapping) -> bool:
    """Whether a Pipfile lists a ``[[source]]`` that isn't PyPI."""
    return _private(s.get("url") for s in _list(data.get("source")) if isinstance(s, dict))


# --- Configuration outside the project ------------------------------------------


def _env_urls(value: str | None) -> list[str]:
    # uv's UV_INDEX entries may be "name=url".
    """Index URLs in an environment variable (space-separated; uv allows ``name=url``)."""
    return [v.split("=", 1)[1] if "=" in v.split("://")[0] else v for v in (value or "").split()]


def _pip_config_files(environ: Mapping[str, str], home: Path) -> Iterator[Path]:
    """pip's configuration files, in pip's own loading order."""
    explicit = environ.get("PIP_CONFIG_FILE")
    if explicit == os.devnull:  # pip's documented way to disable all config files
        return
    if sys.platform == "win32":
        program_data = environ.get("PROGRAMDATA", r"C:\ProgramData")
        yield Path(program_data, "pip", "pip.ini")
        appdata = environ.get("APPDATA")
        yield Path(appdata, "pip", "pip.ini") if appdata else home / "pip" / "pip.ini"
        yield home / "pip" / "pip.ini"
    else:
        for base in environ.get("XDG_CONFIG_DIRS", "/etc/xdg").split(os.pathsep):
            if base:
                yield Path(base, "pip", "pip.conf")
        yield Path("/etc/pip.conf")
        if sys.platform == "darwin":
            yield Path("/Library/Application Support/pip/pip.conf")
            yield home / "Library" / "Application Support" / "pip" / "pip.conf"
        yield home / ".pip" / "pip.conf"
        yield Path(environ.get("XDG_CONFIG_HOME") or home / ".config", "pip", "pip.conf")
    virtual_env = environ.get("VIRTUAL_ENV")
    if virtual_env:
        yield Path(virtual_env, "pip.ini" if sys.platform == "win32" else "pip.conf")
    if explicit:
        yield Path(explicit)


def _pip_config_is_private(path: Path) -> bool:
    """Whether a pip config file sets a non-PyPI index for installs."""
    parser = configparser.RawConfigParser()
    try:
        parser.read(path, encoding="utf-8")
    except (OSError, UnicodeDecodeError, configparser.Error):
        return False
    urls: list[str] = []
    for section in ("global", "install"):
        for key in ("index-url", "extra-index-url", "index_url", "extra_index_url"):
            if parser.has_option(section, key):
                urls.extend(parser.get(section, key).split())
    return _private(urls)


def _uv_config_files(root: Path, environ: Mapping[str, str], home: Path) -> Iterator[Path]:
    """uv's configuration files: the project's, the user's and the system's."""
    if environ.get("UV_NO_CONFIG"):
        return
    if environ.get("UV_CONFIG_FILE"):
        yield Path(environ["UV_CONFIG_FILE"])
        return
    yield root / "uv.toml"
    if sys.platform == "win32":
        appdata = environ.get("APPDATA")
        yield Path(appdata, "uv", "uv.toml") if appdata else home / "uv" / "uv.toml"
        yield Path(environ.get("PROGRAMDATA", r"C:\ProgramData"), "uv", "uv.toml")
    else:
        yield Path(environ.get("XDG_CONFIG_HOME") or home / ".config", "uv", "uv.toml")
        for base in environ.get("XDG_CONFIG_DIRS", "/etc/xdg").split(os.pathsep):
            if base:
                yield Path(base, "uv", "uv.toml")
        yield Path("/etc/uv/uv.toml")


def _uv_toml_is_private(path: Path) -> bool:
    """Whether a uv.toml sets a non-PyPI index."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return False
    return uv_config_is_private(data)


def find_private_index(
    root: Path, environ: Mapping[str, str] | None = None, home: Path | None = None
) -> str | None:
    """Where a non-PyPI index is configured outside the project's dependency files.

    Checks pip's and uv's environment variables and configuration files. Returns a
    short description of the first source found (never the URL), or None.
    """
    environ = os.environ if environ is None else environ
    if home is None:
        try:
            home = Path.home()
        except RuntimeError:  # pragma: no cover - no home directory
            home = Path(os.devnull)
    for var in ("PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL"):
        if _private(_env_urls(environ.get(var))):
            return f"the {var} environment variable"
    for var in ("UV_INDEX", "UV_DEFAULT_INDEX", "UV_INDEX_URL", "UV_EXTRA_INDEX_URL"):
        if _private(_env_urls(environ.get(var))):
            return f"the {var} environment variable"
    for path in _pip_config_files(environ, home):
        if path.is_file() and _pip_config_is_private(path):
            return f"pip configuration ({path})"
    for path in _uv_config_files(root, environ, home):
        if path.is_file() and _uv_toml_is_private(path):
            return f"uv configuration ({path})"
    return None
