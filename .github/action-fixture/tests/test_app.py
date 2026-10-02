from unittest.mock import Mock


def test_user():
    user = Mock()
    user.name = "x"
    assert user.name == "x"
