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
    deps = parse_dependency_file(tmp_path / "pyproject.toml", tmp_path)
    # Path dependencies stay declared (so `import mylib` isn't flagged) but aren't looked up.
    assert [(d.name, d.line, d.validate) for d in deps] == [
        ("httpx", 3, True),
        ("mylib", 4, False),
        ("pytest", 7, True),
    ]


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
    # Every occurrence is reported, so --diff and ignores work per line.
    assert rule_lines(result, "SLOP001") == [7, 8]
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


def test_requirements_ignore_scopes(write, check):
    write(
        "requirements.txt",
        """
        fake-one  # slopcheck: ignore[SLOP001]
        fake-two  # slopcheck: ignore[SLOP051]
        fake-three  # slopcheck: ignore
        """,
    )
    result = check("SLOP001", registry=FakeRegistry(set()))
    # A rule-specific ignore for another rule must not hide SLOP001.
    assert rule_lines(result, "SLOP001") == [2]


def test_requirements_ignore_file(write, check):
    write("requirements.txt", "# slopcheck: ignore-file\nfake-one\nfake-two\n")
    assert check("SLOP001", registry=FakeRegistry(set())).findings == []


def test_ignored_and_external_requirements_stay_declared(write, check):
    write(
        "requirements.txt",
        """
        internal-lib  # slopcheck: ignore
        internal-client @ https://example.com/internal.whl
        git+https://example.com/repo.git#egg=git-thing
        """,
    )
    write("src/app.py", "import internal_lib\nimport internal_client\nimport git_thing\n")
    registry = FakeRegistry(set())
    assert check("SLOP001", registry=registry).findings == []
    assert registry.queries == []  # none of them are looked up on PyPI


def test_private_index_skips_validation(write, check):
    write("requirements.txt", "--extra-index-url https://pkgs.example.com/simple\ncorp-lib\n")
    assert check("SLOP001", registry=FakeRegistry(set())).findings == []


def test_pyproject_line_is_the_dependency_entry(write, check):
    write(
        "pyproject.toml",
        """
        [project]
        name = "demo"
        description = "ghost-lib"
        dependencies = [
            # "ghost-lib",
            "ghost-lib",
            "other-ghost",  # slopcheck: ignore[SLOP001]
        ]
        """,
    )
    result = check("SLOP001", registry=FakeRegistry(set()))
    assert rule_lines(result, "SLOP001") == [6]


def test_pyproject_external_sources(tmp_path, write):
    write(
        "pyproject.toml",
        """
        [project]
        name = "demo"
        dependencies = ["corp-pkg @ https://example.com/corp.whl", "uv-pkg"]

        [tool.uv.sources]
        uv-pkg = { git = "https://example.com/uv-pkg.git" }

        [tool.poetry.dependencies]
        url-dep = { url = "https://example.com/u.whl" }
        private-dep = { version = "^1", source = "corp" }
        """,
    )
    deps = parse_dependency_file(tmp_path / "pyproject.toml", tmp_path)
    assert {d.name: d.validate for d in deps} == {
        "corp-pkg": False,
        "uv-pkg": False,
        "url-dep": False,
        "private-dep": False,
    }


def test_every_import_occurrence_reported(write, check):
    write(
        "src/app.py",
        """
        import ghostpkg_q  # slopcheck: ignore
        import ghostpkg_q
        """,
    )
    result = check("SLOP001", registry=FakeRegistry(set()))
    # The ignored first occurrence must not hide the second one.
    assert rule_lines(result, "SLOP001") == [2]


def test_directives_inside_toml_strings_are_ignored(write, check):
    write(
        "pyproject.toml",
        """
        [project]
        name = "demo"
        description = "# slopcheck: ignore-file"
        readme = \"\"\"
        # slopcheck: ignore-file
        \"\"\"
        dependencies = [
            "ghost-one",
            "ghost-two",  # slopcheck: ignore
            "ghost-three # slopcheck: ignore",
        ]
        """,
    )
    result = check("SLOP001", registry=FakeRegistry(set()))
    assert rule_lines(result, "SLOP001") == [8, 10]


def test_include_group_dependencies_are_checked_once(write, check):
    # Each group is parsed on its own, so included entries are already checked.
    write(
        "pyproject.toml",
        """
        [project]
        name = "demo"

        [dependency-groups]
        dev = ["fake-pkg"]
        lint = [{include-group = "dev"}, "ruff"]
        """,
    )
    result = check("SLOP001", registry=FakeRegistry({"ruff"}))
    assert rule_lines(result, "SLOP001") == [5]


def test_toml_comments():
    from slopcheck.detectors.packages import toml_comments

    text = 'a = "x # no"  # yes\nb = \'# no\'\nc = """\n# no\n"""  # end\n# top'
    assert toml_comments(text) == ["# yes", "", "", "", "# end", "# top"]
