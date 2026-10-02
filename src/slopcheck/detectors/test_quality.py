"""SLOP020/021/022: tests that pass without testing anything.

All three rules are deliberately conservative. A test is only flagged when
every assertion in it is meaningless, never when one meaningful check exists.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from slopcheck.models import Finding
from slopcheck.source import SourceFile

MOCK_FACTORIES = {"Mock", "MagicMock", "AsyncMock", "NonCallableMock", "create_autospec"}
PATCH_NAMES = {"patch", "patch.object", "patch.dict", "patch.multiple"}
SWALLOWING_EXCEPTIONS = {"Exception", "BaseException", "AssertionError"}
FAIL_CALLS = {"fail", "skip", "xfail"}


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _root_name(node: ast.AST) -> str | None:
    while isinstance(node, (ast.Attribute, ast.Subscript, ast.Call)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None


def _is_mock_factory(call: ast.AST) -> bool:
    return isinstance(call, ast.Call) and _dotted(call.func).split(".")[-1] in MOCK_FACTORIES


def _is_patch_decorator(dec: ast.AST) -> bool:
    target = dec.func if isinstance(dec, ast.Call) else dec
    name = _dotted(target)
    return any(name == p or name.endswith("." + p) for p in PATCH_NAMES)


def _test_functions(tree: ast.Module) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test"
        ):
            yield node


def _walk_own_body(func: ast.AST) -> Iterator[ast.AST]:
    """Walk a function's body without descending into nested functions or classes."""
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield node
        stack.extend(ast.iter_child_nodes(node))


def _is_assert_call(call: ast.Call) -> bool:
    """self.assertX(...), mock.assert_called_*(...), pytest.approx is not an assertion."""
    if not isinstance(call.func, ast.Attribute):
        return False
    return call.func.attr.startswith("assert")


def _assertions(func: ast.AST) -> list[ast.AST]:
    found: list[ast.AST] = []
    for node in _walk_own_body(func):
        if isinstance(node, ast.Assert) or (isinstance(node, ast.Call) and _is_assert_call(node)):
            found.append(node)
    return found


def _uses_pytest_raises_or_fail(func: ast.AST) -> bool:
    for node in _walk_own_body(func):
        if isinstance(node, ast.Call):
            name = _dotted(node.func)
            last = name.split(".")[-1]
            if last in {"raises", "warns", "deprecated_call", "assertRaises", "assertWarns"}:
                return True
            if last in FAIL_CALLS and (name.startswith("pytest.") or name.startswith("self.")):
                return True
    return False


# --- SLOP020 -------------------------------------------------------------------


def _mock_names(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names: set[str] = set()
    for node in _walk_own_body(func):
        if isinstance(node, ast.Assign) and _is_mock_factory(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and node.value and _is_mock_factory(node.value):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
        elif (
            isinstance(node, ast.withitem)
            and _is_mock_factory(node.context_expr)
            and isinstance(node.optional_vars, ast.Name)
        ):
            names.add(node.optional_vars.id)
    if any(_is_patch_decorator(d) for d in func.decorator_list):
        for arg in func.args.args + func.args.kwonlyargs:
            if arg.arg.startswith("mock"):
                names.add(arg.arg)
    return names


def _names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _assertion_subjects(node: ast.AST) -> set[str]:
    """Names an assertion actually inspects (ignores the `self` in self.assertEqual)."""
    if isinstance(node, ast.Assert):
        return _names_in(node.test)
    assert isinstance(node, ast.Call)
    names: set[str] = set()
    for arg in [*node.args, *(k.value for k in node.keywords)]:
        names |= _names_in(arg)
    # mock.assert_called_once() inspects the mock it is called on.
    if isinstance(node.func, ast.Attribute) and _dotted(node.func.value) != "self":
        names |= _names_in(node.func.value)
    return names


def _calls_real_code(func: ast.AST, mocks: set[str], assertion_nodes: set[int]) -> bool:
    """True if the test calls anything other than mock factories and mock methods."""
    for node in _walk_own_body(func):
        if not isinstance(node, ast.Call) or id(node) in assertion_nodes:
            continue
        if _is_mock_factory(node) or _is_patch_decorator(node):
            continue
        root = _root_name(node.func)
        if root in mocks:
            continue
        return True
    return False


def check_mock_only_tests(src: SourceFile) -> Iterator[Finding]:
    if not src.is_test_file:
        return
    for func in _test_functions(src.tree):
        mocks = _mock_names(func)
        if not mocks:
            continue
        asserts = _assertions(func)
        if not asserts:
            continue
        subjects = [_assertion_subjects(a) for a in asserts]
        if not all(s and s <= mocks for s in subjects):
            continue
        assertion_ids = {id(n) for a in asserts for n in ast.walk(a)}
        if _calls_real_code(func, mocks, assertion_ids):
            continue
        yield Finding(
            "SLOP020",
            src.rel,
            func.lineno,
            func.col_offset + 1,
            f"Test '{func.name}' only asserts on its own mocks and never calls real code",
            end_line=func.end_lineno,
        )


# --- SLOP021 -------------------------------------------------------------------

TRUTHY_ASSERT_METHODS = {"assertTrue", "assert_", "failUnless"}


def _is_trivially_true(node: ast.AST) -> bool:
    if isinstance(node, ast.Assert):
        test = node.test
    elif (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in TRUTHY_ASSERT_METHODS
        and node.args
    ):
        test = node.args[0]
    elif (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "assertEqual"
        and len(node.args) >= 2
    ):
        return ast.dump(node.args[0]) == ast.dump(node.args[1]) and not _has_call(node.args[0])
    else:
        return False

    if isinstance(test, ast.Constant):
        return bool(test.value)
    # assert x == x  (same expression on both sides, no calls that could have side effects)
    if (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], (ast.Eq, ast.Is, ast.GtE, ast.LtE))
    ):
        left, right = test.left, test.comparators[0]
        return ast.dump(left) == ast.dump(right) and not _has_call(left)
    return False


def _has_call(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Call) for n in ast.walk(node))


def _unused_call_results(func: ast.AST) -> list[str]:
    """Variables assigned from a call and never read: `result = run(); assert True`."""
    assigned: dict[str, ast.AST] = {}
    loaded: set[str] = set()
    for node in _walk_own_body(func):
        if isinstance(node, ast.Assign) and isinstance(node.value, (ast.Call, ast.Await)):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned[target.id] = node
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            loaded.add(node.id)
    return [name for name in assigned if name not in loaded and not name.startswith("_")]


def check_trivial_assertions(src: SourceFile) -> Iterator[Finding]:
    if not src.is_test_file:
        return
    for func in _test_functions(src.tree):
        asserts = _assertions(func)
        if not asserts or not all(_is_trivially_true(a) for a in asserts):
            continue
        if _uses_pytest_raises_or_fail(func):
            continue
        assertion_ids = {id(n) for a in asserts for n in ast.walk(a)}
        calls_code = _calls_real_code(func, set(), assertion_ids)
        unused = _unused_call_results(func)
        # `do_something(); assert True` is a deliberate "doesn't crash" smoke test.
        # Only flag tests that call nothing, or compute a result and ignore it.
        if calls_code and not unused:
            continue
        detail = (
            f"computes '{unused[0]}' but never checks it"
            if unused
            else "only has assertions that are always true"
        )
        first = asserts[0]
        yield Finding(
            "SLOP021",
            src.rel,
            first.lineno,
            first.col_offset + 1,
            f"Test '{func.name}' {detail}",
            end_line=func.end_lineno,
        )


# --- SLOP022 -------------------------------------------------------------------


def _handler_swallows(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        caught = {"BaseException"}
    elif isinstance(handler.type, ast.Tuple):
        caught = {_dotted(e).split(".")[-1] for e in handler.type.elts}
    else:
        caught = {_dotted(handler.type).split(".")[-1]}
    if not caught & SWALLOWING_EXCEPTIONS:
        return False
    for node in ast.walk(handler):
        if isinstance(node, ast.Raise):
            return False
        if isinstance(node, ast.Call):
            last = _dotted(node.func).split(".")[-1]
            if last in FAIL_CALLS or _is_assert_call(node):
                return False
        if isinstance(node, ast.Assert):
            return False
    return True


def _is_assertion(node: ast.AST) -> bool:
    return isinstance(node, ast.Assert) or (isinstance(node, ast.Call) and _is_assert_call(node))


def check_swallowed_assertions(src: SourceFile) -> Iterator[Finding]:
    if not src.is_test_file:
        return
    for func in _test_functions(src.tree):
        all_asserts = {id(n) for n in _walk_own_body(func) if _is_assertion(n)}
        if not all_asserts or _uses_pytest_raises_or_fail(func):
            continue
        swallowed: set[int] = set()
        first_handler: ast.ExceptHandler | None = None
        for node in _walk_own_body(func):
            if not isinstance(node, ast.Try):
                continue
            handlers = [h for h in node.handlers if _handler_swallows(h)]
            if not handlers:
                continue
            guarded = {id(n) for stmt in node.body for n in ast.walk(stmt) if _is_assertion(n)}
            if guarded:
                swallowed |= guarded
                if first_handler is None or handlers[0].lineno < first_handler.lineno:
                    first_handler = handlers[0]
        # If any assertion can still fail, the test can still fail.
        if first_handler is None or swallowed != all_asserts:
            continue
        yield Finding(
            "SLOP022",
            src.rel,
            first_handler.lineno,
            first_handler.col_offset + 1,
            f"Test '{func.name}' catches assertion failures without re-raising, "
            "so it can never fail",
            end_line=func.end_lineno,
        )
