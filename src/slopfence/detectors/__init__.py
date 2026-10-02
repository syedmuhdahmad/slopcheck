from slopfence.detectors.code_quality import check_stub_functions, check_swallowed_exceptions
from slopfence.detectors.test_quality import (
    check_mock_only_tests,
    check_swallowed_assertions,
    check_trivial_assertions,
)
from slopfence.detectors.text_patterns import check_chat_leftovers, check_placeholders

# Per-file detectors that need nothing but the parsed source.
FILE_DETECTORS = {
    "SLOP010": check_placeholders,
    "SLOP011": check_stub_functions,
    "SLOP020": check_mock_only_tests,
    "SLOP021": check_trivial_assertions,
    "SLOP022": check_swallowed_assertions,
    "SLOP040": check_swallowed_exceptions,
    "SLOP051": check_chat_leftovers,
}

__all__ = ["FILE_DETECTORS"]
