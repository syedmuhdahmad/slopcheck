from slopcheck.detectors.test_quality import (
    check_mock_only_tests,
    check_swallowed_assertions,
    check_trivial_assertions,
)
from slopcheck.detectors.text_patterns import check_chat_leftovers, check_placeholders

# Per-file detectors that need nothing but the parsed source.
FILE_DETECTORS = {
    "SLOP010": check_placeholders,
    "SLOP020": check_mock_only_tests,
    "SLOP021": check_trivial_assertions,
    "SLOP022": check_swallowed_assertions,
    "SLOP051": check_chat_leftovers,
}

__all__ = ["FILE_DETECTORS"]
