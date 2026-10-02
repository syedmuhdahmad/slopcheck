"""PyPI existence lookups with an on-disk cache.

Network failures never produce findings: an unknown answer is treated as
"exists", because a false alarm is worse than a missed one.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol

from slopfence import __version__

EXISTS_TTL = 7 * 24 * 3600
MISSING_TTL = 24 * 3600


def normalize(name: str) -> str:
    """PEP 503 name normalization."""
    return re.sub(r"[-_.]+", "-", name).lower()


class Registry(Protocol):
    def exists(self, name: str) -> bool | None:
        """True/False if known, None if the registry could not be reached."""


class OfflineRegistry:
    def exists(self, name: str) -> bool | None:
        return None


class PyPIRegistry:
    def __init__(self, cache_dir: Path | None = None, timeout: float = 5.0) -> None:
        if cache_dir is None:
            base = os.environ.get("SLOPFENCE_CACHE_DIR") or os.environ.get("XDG_CACHE_HOME")
            cache_dir = Path(base) / "slopfence" if base else Path.home() / ".cache" / "slopfence"
        self.cache_file = cache_dir / "pypi.json"
        self.timeout = timeout
        self._cache: dict[str, list] = self._load()
        self._dirty = False
        self._unreachable = False

    def _load(self) -> dict[str, list]:
        try:
            return json.loads(self.cache_file.read_text())
        except (OSError, ValueError):
            return {}

    def save(self) -> None:
        if not self._dirty:
            return
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(json.dumps(self._cache))
        except OSError:
            pass

    def exists(self, name: str) -> bool | None:
        key = normalize(name)
        cached = self._cache.get(key)
        now = time.time()
        if cached:
            found, stamp = cached
            if now - stamp < (EXISTS_TTL if found else MISSING_TTL):
                return found
        if self._unreachable:
            return None
        found = self._query(key)
        if found is not None:
            self._cache[key] = [found, now]
            self._dirty = True
        return found

    def _query(self, key: str) -> bool | None:
        req = urllib.request.Request(
            f"https://pypi.org/pypi/{key}/json",
            method="HEAD",
            headers={"User-Agent": f"slopfence/{__version__}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 400
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return False
            return None
        except (urllib.error.URLError, TimeoutError, OSError):
            # Stop hammering a registry we cannot reach for the rest of the run.
            self._unreachable = True
            return None
