from slopcheck.detectors.packages import parse_dependency_file
from tests.conftest import FakeRegistry, rule_lines


def test_requirements_nonexistent_dependency(write, check):
    write(
        "requirements.txt",
        """
        # web deps
        requests>=2.31
        flask-jwt-simple-auth==1.2.0
        -r other.txt
        git+https://github.com/org/repo.git
        local-thing @ https://example.com/pkg.whl
        made-up-but-ignored  # slopcheck: ignore
        """,
    )
    result = check("SLOP001", registry=FakeRegistry({"requests"}))
    assert rule_lines(result, "SLOP001") == [3]
    assert "flask-jwt-simple-auth" in result.findings[0].message


def test_pyproject_dependencies(write, check, tmp_path):
    write(
        "pyproject.toml",
        """
        [project]
        name = "demo"
        dependencies = ["requests>=2", "totally-fake-pkg[extra]>=1"]

        [project.optional-dependencies]
        dev = ["pytest", "demo[extra]"]

        [dependency-groups]
        lint = ["ruff", {include-group = "dev"}]
        """,
    )
    deps = [d.name for d in parse_dependency_file(tmp_path / "pyproject.toml", tmp_path)]
    assert deps == ["requests", "totally-fake-pkg", "pytest", "ruff"]
    result = check("SLOP001", registry=FakeRegistry({"requests", "pytest", "ruff"}))
    assert rule_lines(result, "SLOP001") == [3]


def test_poetry_dependencies(tmp_path, write):
    write(
        "pyproject.toml",
        """
        [tool.poetry.dependencies]
        python = "^3.11"
        httpx = "^0.27"
        mylib = { path = "../mylib" }

        [tool.poetry.group.dev.dependencies]
        pytest = "^8"
        """,
    )
    deps = [d.name for d in parse_dependency_file(tmp_path / "pyproject.toml", tmp_path)]
    assert deps == ["httpx", "pytest"]


def test_hallucinated_import_flagged(write, check):
    write(
        "src/app.py",
        """
        import os
        import json
        from collections import OrderedDict
        import yaml
        import utils
        from . import sibling
        import fastjsonvalidatorx
        from fastjsonvalidatorx.core import validate
        """,
    )
    write("src/utils.py", "")
    registry = FakeRegistry(set())
    result = check("SLOP001", registry=registry)
    assert rule_lines(result, "SLOP001") == [7]
    # stdlib, local modules and known aliases are never looked up.
    assert set(registry.queries) == {"fastjsonvalidatorx"}


def test_installed_and_declared_imports_not_flagged(write, check):
    write("requirements.txt", "my-declared-lib\n")
    write("src/app.py", "import pytest\nimport my_declared_lib\n")
    registry = FakeRegistry({"my-declared-lib"})
    assert check("SLOP001", registry=registry).findings == []
    assert "pytest" not in registry.queries


def test_unreachable_registry_never_flags(write, check):
    class Down:
        def exists(self, name):
            return None

    write("requirements.txt", "anything-at-all\n")
    write("src/app.py", "import nonexistent_xyz\n")
    assert check("SLOP001", registry=Down()).findings == []


def test_offline_skips_lookups(write, check):
    write("requirements.txt", "fake-pkg\n")
    write("src/app.py", "import fake_pkg_two\n")
    assert check("SLOP001").findings == []


def test_single_file_still_knows_project_modules(write, tmp_path):
    from slopcheck.engine import run

    write("requirements.txt", "my-internal-dep\n")
    write("src/mypkg/__init__.py", "")
    write("src/mypkg/core.py", "")
    app = write("src/app.py", "import mypkg.core\nimport my_internal_dep\nimport invented_pkg_zz\n")
    registry = FakeRegistry({"my-internal-dep"})
    result = run([app], tmp_path, registry, select=["SLOP001"])
    assert rule_lines(result, "SLOP001") == [3]
    assert set(registry.queries) == {"invented_pkg_zz", "invented-pkg-zz"}
