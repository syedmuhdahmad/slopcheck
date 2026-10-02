import pytest

from tests.conftest import rule_lines


@pytest.mark.parametrize(
    "comment",
    [
        "# In a real implementation, validate the token against the server",
        "# In a production environment you would use a database",
        "# Simplified implementation for demo",
        "# This is a placeholder implementation",
        "# Replace this with your actual API call",
        "# Your logic goes here",
        "# ... rest of the code",
        "# Add your validation here",
        "# placeholder logic, swap out later",
    ],
)
def test_placeholder_flagged(write, check, comment):
    write("src/app.py", f"def f():\n    {comment}\n    return True\n")
    assert rule_lines(check("SLOP010"), "SLOP010") == [2]


@pytest.mark.parametrize(
    "comment",
    [
        # Real-world comments from human-written projects that must stay quiet.
        "# TODO: Implement this in C.",
        "# In this case, Ansible will inject the omit-placeholder value",
        "# This is a stub package designed to roughly emulate the _yaml module",
        "# The `Omit` placeholder value will be visible to Jinja plugins",
        "# Real implementation lives in the C extension",
    ],
)
def test_placeholder_not_flagged(write, check, comment):
    write("src/app.py", f"def f():\n    {comment}\n    return True\n")
    assert check("SLOP010").findings == []


def test_placeholder_in_docstring(write, check):
    write(
        "src/app.py",
        '''
        def charge(card):
            """Charge the card.

            In a real application this would call the payment provider.
            """
            return {"ok": True}
        ''',
    )
    assert rule_lines(check("SLOP010"), "SLOP010") == [4]


def test_placeholder_skipped_in_tests(write, check):
    write("tests/test_app.py", "def test_x():\n    # in a real app this would hit the db\n")
    assert check("SLOP010").findings == []


def test_placeholder_in_string_literal_not_flagged(write, check):
    write("src/app.py", 'MSG = "In a real implementation you would see this"\n')
    assert check("SLOP010").findings == []


@pytest.mark.parametrize(
    "comment",
    [
        "# Certainly! Here is the code:",
        "# Sure, here's how to do it",
        "# Here's the updated function that handles retries",
        "# Below is the complete implementation",
        "# As an AI language model, I cannot run this",
        "# I hope this helps!",
        "# Let me know if you have any other questions.",
        "# I apologize for the confusion earlier",
    ],
)
def test_chat_leftover_flagged(write, check, comment):
    write("src/app.py", f"x = 1\n{comment}\n")
    assert rule_lines(check("SLOP051"), "SLOP051") == [2]


@pytest.mark.parametrize(
    "comment",
    [
        # Human prose found in CPython, dateutil, psutil, launchpadlib, setuptools.
        "# Of course, you still have to use your head!",
        "# of course, first we have to figure out all the other things",
        "# always in gmt time. Let me know if you have comments",
        "# Here's the new credential.",
        "# Fields are explained in 'man proc'; here is an updated list",
        "# Sure enough, the cache was stale",
    ],
)
def test_chat_leftover_not_flagged(write, check, comment):
    write("src/app.py", f"x = 1\n{comment}\n")
    assert check("SLOP051").findings == []


def test_ignore_comment_on_line(write, check):
    write(
        "src/app.py",
        """
        # In a real implementation, retry.  # slopcheck: ignore[SLOP010]
        # I hope this helps  # slopcheck: ignore
        # In a real implementation, log it.  # slopcheck: ignore[SLOP051]
        """,
    )
    assert rule_lines(check(), "SLOP010") == [3]
    assert rule_lines(check(), "SLOP051") == []


def test_ignore_file(write, check):
    write("src/app.py", "# slopcheck: ignore-file\n# I hope this helps!\n")
    assert check().findings == []


def test_docstring_escapes_use_physical_lines(write, check):
    write(
        "src/app.py",
        '''
        def f():
            "Intro\\nI hope this helps!"

        def g():
            """Start \\
        I hope this helps!"""
        ''',
    )
    assert rule_lines(check("SLOP051"), "SLOP051") == [2, 6]


def test_non_utf8_and_bom_files_are_checked(tmp_path, check):
    (tmp_path / "latin.py").write_bytes(
        b"# -*- coding: latin-1 -*-\nNAME = 'caf\xe9'\n# I hope this helps!\n"
    )
    (tmp_path / "bom.py").write_bytes(b"\xef\xbb\xbf# I hope this helps!\n")
    result = check("SLOP051")
    assert result.parse_errors == []
    assert sorted((f.path, f.line) for f in result.findings) == [("bom.py", 1), ("latin.py", 3)]
