"""What slopfence sends to PyPI (#34): import lookups are opt-in."""

import json

import pytest

from slopfence.cli import main
from slopfence.registry import PyPIRegistry


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A project importing a private package, with PyPI answers pinned in the cache."""
    (tmp_path / "requirements.txt").write_text("requests\n")
    (tmp_path / "app.py").write_text("import requests\nimport corp_secret_auth\n")
    cache = tmp_path / "cache" / "slopfence"
    cache.mkdir(parents=True)
    far_future = 9e12
    (cache / "pypi.json").write_text(
        json.dumps({"requests": [True, far_future], "corp-secret-auth": [False, far_future]})
    )
    monkeypatch.setenv("SLOPFENCE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.chdir(tmp_path)

    asked: list[str] = []
    real_exists = PyPIRegistry.exists

    def exists(self, name):
        asked.append(name)
        return real_exists(self, name)

    def no_network(self, key):
        raise AssertionError(f"unexpected network lookup for {key!r}")

    monkeypatch.setattr(PyPIRegistry, "exists", exists)
    monkeypatch.setattr(PyPIRegistry, "_query", no_network)
    return tmp_path, asked


def _findings(capsys):
    return [(f["path"], f["line"]) for f in json.loads(capsys.readouterr().out)["findings"]]


def test_imports_never_reach_the_registry_by_default(project, capsys):
    _, asked = project
    assert main([".", "--format", "json"]) == 0
    assert _findings(capsys) == []
    # Only the declared dependency was looked up; the import name stayed local.
    assert asked == ["requests"]


def test_check_imports_opt_in_from_cli_and_config(project, capsys):
    root, asked = project
    assert main([".", "--format", "json", "--check-imports"]) == 1
    assert _findings(capsys) == [("app.py", 2)]
    assert "corp_secret_auth" in asked

    (root / "pyproject.toml").write_text("[tool.slopfence]\ncheck-imports = true\n")
    assert main([".", "--format", "json"]) == 1
    assert _findings(capsys) == [("app.py", 2)]

    asked.clear()
    assert main([".", "--format", "json", "--no-check-imports"]) == 0
    assert _findings(capsys) == []
    assert "corp_secret_auth" not in asked


def test_offline_makes_no_lookups_at_all(project, capsys):
    _, asked = project
    assert main([".", "--format", "json", "--offline", "--check-imports"]) == 0
    assert asked == []
