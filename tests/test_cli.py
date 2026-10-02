import json
import subprocess

import pytest

from slopcheck import diff as diffmod
from slopcheck.cli import main

SLOPPY = """\
def charge(card):
    # In a real implementation, call the payment provider
    return True
"""


def test_exit_codes(tmp_path, capsys):
    (tmp_path / "clean.py").write_text("x = 1\n")
    assert main([str(tmp_path), "--offline"]) == 0
    (tmp_path / "app.py").write_text(SLOPPY)
    assert main([str(tmp_path), "--offline"]) == 1
    assert main([str(tmp_path), "--offline", "--exit-zero"]) == 0
    assert main([str(tmp_path / "missing")]) == 2
    out = capsys.readouterr().out
    assert "SLOP010" in out
    assert "1 issue (1 medium)" in out


def test_select_and_ignore(tmp_path, capsys):
    (tmp_path / "app.py").write_text(SLOPPY + "# I hope this helps!\n")
    main([str(tmp_path), "--offline", "--format", "json", "--select", "SLOP051"])
    rules = {f["rule"] for f in json.loads(capsys.readouterr().out)["findings"]}
    assert rules == {"SLOP051"}
    main([str(tmp_path), "--offline", "--format", "json", "--ignore", "slop051"])
    rules = {f["rule"] for f in json.loads(capsys.readouterr().out)["findings"]}
    assert rules == {"SLOP010"}


def test_unknown_rule_is_an_error(tmp_path):
    with pytest.raises(SystemExit):
        main([str(tmp_path), "--select", "SLOP999"])


def test_sarif_output(tmp_path):
    (tmp_path / "app.py").write_text(SLOPPY)
    out = tmp_path / "report.sarif"
    main([str(tmp_path), "--offline", "--format", "sarif", "-o", str(out)])
    doc = json.loads(out.read_text())
    assert doc["version"] == "2.1.0"
    run = doc["runs"][0]
    assert run["tool"]["driver"]["name"] == "slopcheck"
    [res] = run["results"]
    assert res["ruleId"] == "SLOP010"
    assert res["level"] == "warning"
    loc = res["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"] == "app.py"
    assert loc["region"]["startLine"] == 2


def test_parse_unified_diff():
    text = """\
diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,0 +2,3 @@ def f():
+a
+b
+c
@@ -10 +14 @@
+d
diff --git a/old.py b/old.py
--- a/old.py
+++ /dev/null
@@ -1,2 +0,0 @@
"""
    changed = diffmod.parse_unified_diff(text)
    assert changed == {"app.py": {2, 3, 4, 14}}
    assert diffmod.touches(changed, "app.py", 1, 2)
    assert not diffmod.touches(changed, "app.py", 5, 13)
    assert not diffmod.touches(changed, "other.py", 1, None)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_diff_mode_only_reports_changed_lines(tmp_path, capsys, monkeypatch):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "old.py").write_text("# In a real implementation, do X\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "init")
    _git(tmp_path, "switch", "-q", "-c", "feature")
    (tmp_path / "old.py").write_text(
        "# In a real implementation, do X\nx = 1\n# I hope this helps!\n"
    )
    (tmp_path / "new.py").write_text("# Simplified implementation for demo\n")

    monkeypatch.chdir(tmp_path)
    assert main([".", "--offline", "--diff", "main", "--format", "json"]) == 1
    findings = json.loads(capsys.readouterr().out)["findings"]
    assert sorted((f["path"], f["line"], f["rule"]) for f in findings) == [
        ("new.py", 1, "SLOP010"),
        ("old.py", 3, "SLOP051"),
    ]


def test_diff_with_bad_ref(tmp_path, monkeypatch):
    _git(tmp_path, "init", "-q")
    monkeypatch.chdir(tmp_path)
    assert main([".", "--offline", "--diff", "no-such-ref"]) == 2


def test_list_rules(capsys):
    assert main(["--list-rules"]) == 0
    assert "SLOP001" in capsys.readouterr().out
