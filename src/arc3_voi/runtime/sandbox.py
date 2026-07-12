"""Static validation for generated hypothesis programs.

This module deliberately accepts a small, expression-oriented subset of Python.
Programs may define pure helper functions plus the required ``predict`` and
``goal_value`` functions.  They cannot import modules or reach Python's dynamic
introspection, I/O, process, or code-generation APIs.

Static validation is one layer of the sandbox.  Validated programs are still run
in the isolated worker from :mod:`arc3_voi.runtime.worker`, with a wall-clock
deadline and a best-effort process memory limit.
"""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from enum import StrEnum

MAX_SOURCE_CHARS = 65_536
MAX_AST_NODES = 4_096

# The generated program sees only these builtins.  Keep this in sync with the
# concrete mapping installed by runtime.worker.
SAFE_BUILTIN_CALLS = frozenset(
    {
        "abs",
        "all",
        "any",
        "bool",
        "dict",
        "enumerate",
        "filter",
        "float",
        "frozenset",
        "int",
        "isinstance",
        "len",
        "list",
        "map",
        "max",
        "min",
        "range",
        "reversed",
        "round",
        "set",
        "slice",
        "sorted",
        "str",
        "sum",
        "tuple",
        "zip",
    }
)

# NumPy is exposed through a facade containing exactly these names.  In
# particular, file loading/saving, ctypes, random state, and Python callbacks are
# not available.
SAFE_NUMPY_ATTRIBUTES = frozenset(
    {
        "abs",
        "add",
        "all",
        "allclose",
        "any",
        "arange",
        "argmax",
        "argmin",
        "argwhere",
        "array",
        "array_equal",
        "asarray",
        "argsort",
        "bool_",
        "bincount",
        "clip",
        "concatenate",
        "copy",
        "count_nonzero",
        "diag",
        "divide",
        "empty_like",
        "equal",
        "expand_dims",
        "eye",
        "flip",
        "fliplr",
        "flipud",
        "float32",
        "float64",
        "full",
        "full_like",
        "hstack",
        "indices",
        "int8",
        "int16",
        "int32",
        "int64",
        "isclose",
        "isfinite",
        "isinf",
        "isnan",
        "isin",
        "linspace",
        "logical_and",
        "logical_not",
        "logical_or",
        "max",
        "maximum",
        "mean",
        "median",
        "meshgrid",
        "min",
        "minimum",
        "mod",
        "multiply",
        "ndarray",
        "newaxis",
        "nonzero",
        "not_equal",
        "ones",
        "ones_like",
        "pad",
        "repeat",
        "reshape",
        "roll",
        "rot90",
        "select",
        "sign",
        "sort",
        "split",
        "squeeze",
        "stack",
        "std",
        "subtract",
        "sum",
        "take",
        "tile",
        "trace",
        "transpose",
        "tril",
        "triu",
        "uint8",
        "uint16",
        "uint32",
        "uint64",
        "unique",
        "vstack",
        "where",
        "zeros",
        "zeros_like",
    }
)

# Method calls are permitted only on sanitized records and ordinary containers
# or arrays.  Dangerous ndarray methods such as dump/tofile are absent.
SAFE_METHOD_CALLS = frozenset(
    {
        "all",
        "add",
        "any",
        "append",
        "argmax",
        "argmin",
        "astype",
        "copy",
        "count",
        "discard",
        "extend",
        "flatten",
        "get",
        "index",
        "items",
        "keys",
        "max",
        "mean",
        "min",
        "nonzero",
        "reshape",
        "std",
        "sum",
        "tolist",
        "values",
    }
)

# Attribute reads are useful for dataclass-like History/Action values and NumPy
# array metadata.  Inputs are converted to inert records before user code sees
# them, and stores through attributes are never allowed.
SAFE_DATA_ATTRIBUTES = frozenset(
    {
        "T",
        "actions",
        "available_action_sets",
        "available_actions",
        "dtype",
        "frames",
        "game_state",
        "game_states",
        "kind",
        "level_delta",
        "level_deltas",
        "levels",
        "current_level",
        "memory",
        "ndim",
        "next_grid",
        "row",
        "shape",
        "size",
        "stable_frames",
        "win_levels",
        "x",
        "y",
        "col",
    }
) | SAFE_METHOD_CALLS

_REQUIRED_SIGNATURES = {"predict": ("history", "action"), "goal_value": ("history",)}
_RESERVED_NAMES = SAFE_BUILTIN_CALLS | {"np", "__builtins__"}
_FORBIDDEN_CAPABILITY_NAMES = frozenset(
    {
        "breakpoint",
        "compile",
        "eval",
        "exec",
        "getattr",
        "globals",
        "input",
        "locals",
        "open",
        "os",
        "pathlib",
        "setattr",
        "shutil",
        "socket",
        "subprocess",
        "sys",
        "vars",
    }
)


class ValidationCode(StrEnum):
    """Machine-readable reason that generated source was rejected."""

    SYNTAX = "syntax"
    SOURCE_TOO_LARGE = "source_too_large"
    AST_TOO_LARGE = "ast_too_large"
    DISALLOWED_NODE = "disallowed_node"
    DISALLOWED_NAME = "disallowed_name"
    DISALLOWED_ATTRIBUTE = "disallowed_attribute"
    DISALLOWED_CALL = "disallowed_call"
    INVALID_TOP_LEVEL = "invalid_top_level"
    INVALID_CONTRACT = "invalid_contract"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One source validation failure."""

    code: ValidationCode
    message: str
    line: int | None = None
    column: int | None = None


class SandboxValidationError(ValueError):
    """Raised when generated source is outside the accepted language subset."""

    def __init__(self, issues: tuple[ValidationIssue, ...]):
        self.issues = issues
        summary = "; ".join(issue.message for issue in issues[:3])
        if len(issues) > 3:
            summary += f"; and {len(issues) - 3} more issue(s)"
        super().__init__(summary)


@dataclass(frozen=True, slots=True)
class ValidatedProgram:
    """Canonical, validated representation used by the worker."""

    canonical_source: str
    canonical_ast: str
    node_count: int
    sha256: str


# Operators and contexts appear as nodes during ast.walk, so they must be
# explicitly admitted alongside the executable syntax nodes.
_ALLOWED_NODE_TYPES = (
    ast.Module,
    ast.FunctionDef,
    ast.arguments,
    ast.arg,
    ast.Return,
    ast.Assign,
    ast.AnnAssign,
    ast.AugAssign,
    ast.Expr,
    ast.If,
    ast.For,
    ast.While,
    ast.Break,
    ast.Continue,
    ast.Pass,
    ast.BoolOp,
    ast.BinOp,
    ast.UnaryOp,
    ast.IfExp,
    ast.Dict,
    ast.Set,
    ast.List,
    ast.Tuple,
    ast.Compare,
    ast.Call,
    ast.keyword,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Attribute,
    ast.Subscript,
    ast.Slice,
    ast.Starred,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.comprehension,
    ast.JoinedStr,
    ast.FormattedValue,
    ast.And,
    ast.Or,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.LShift,
    ast.RShift,
    ast.BitOr,
    ast.BitXor,
    ast.BitAnd,
    ast.MatMult,
    ast.Invert,
    ast.Not,
    ast.UAdd,
    ast.USub,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Is,
    ast.IsNot,
    ast.In,
    ast.NotIn,
)


def _issue(code: ValidationCode, message: str, node: ast.AST | None = None) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        message=message,
        line=getattr(node, "lineno", None),
        column=getattr(node, "col_offset", None),
    )


def _target_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Tuple | ast.List):
        return {name for item in target.elts for name in _target_names(item)}
    return set()


def _is_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.List | ast.Tuple | ast.Set):
        return all(_is_literal(item) for item in node.elts)
    if isinstance(node, ast.Dict):
        return all(key is None or _is_literal(key) for key in node.keys) and all(
            _is_literal(value) for value in node.values
        )
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
        return _is_literal(node.operand)
    return False


class _ProgramValidator(ast.NodeVisitor):
    def __init__(self, helper_names: frozenset[str]):
        self.helper_names = helper_names
        self.issues: list[ValidationIssue] = []
        self._function_depth = 0

    def generic_visit(self, node: ast.AST) -> None:
        if not isinstance(node, _ALLOWED_NODE_TYPES):
            self.issues.append(
                _issue(
                    ValidationCode.DISALLOWED_NODE,
                    f"{type(node).__name__} is not allowed in generated programs",
                    node,
                )
            )
            return
        super().generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._function_depth:
            self.issues.append(
                _issue(
                    ValidationCode.DISALLOWED_NODE,
                    "nested function definitions are not allowed",
                    node,
                )
            )
            return
        if node.decorator_list:
            self.issues.append(
                _issue(ValidationCode.DISALLOWED_NODE, "function decorators are not allowed", node)
            )
        if node.name.startswith("_") or node.name in _FORBIDDEN_CAPABILITY_NAMES:
            self.issues.append(
                _issue(
                    ValidationCode.DISALLOWED_NAME,
                    f"private function name {node.name!r} is not allowed",
                    node,
                )
            )
        if node.name in _RESERVED_NAMES:
            self.issues.append(
                _issue(
                    ValidationCode.DISALLOWED_NAME,
                    f"function name {node.name!r} shadows a sandbox capability",
                    node,
                )
            )
        if node.args.vararg is not None or node.args.kwarg is not None or node.args.kwonlyargs:
            self.issues.append(
                _issue(
                    ValidationCode.INVALID_CONTRACT,
                    f"function {node.name!r} may use positional parameters only",
                    node,
                )
            )
        positional = [*node.args.posonlyargs, *node.args.args]
        for argument in positional:
            if argument.arg.startswith("_") or argument.arg in (
                _RESERVED_NAMES | self.helper_names
            ):
                self.issues.append(
                    _issue(
                        ValidationCode.DISALLOWED_NAME,
                        f"argument {argument.arg!r} shadows or exposes a restricted name",
                        argument,
                    )
                )
        for default in [*node.args.defaults, *node.args.kw_defaults]:
            if default is not None and not _is_literal(default):
                self.issues.append(
                    _issue(
                        ValidationCode.DISALLOWED_NODE,
                        "function defaults must be literals",
                        default,
                    )
                )
        self._function_depth += 1
        self.generic_visit(node)
        self._function_depth -= 1

    def visit_Name(self, node: ast.Name) -> None:
        if node.id.startswith("_") or node.id in _FORBIDDEN_CAPABILITY_NAMES:
            self.issues.append(
                _issue(
                    ValidationCode.DISALLOWED_NAME,
                    f"private name {node.id!r} is not allowed",
                    node,
                )
            )
        if isinstance(node.ctx, ast.Store) and node.id in (_RESERVED_NAMES | self.helper_names):
            self.issues.append(
                _issue(
                    ValidationCode.DISALLOWED_NAME,
                    f"assignment to reserved callable {node.id!r} is not allowed",
                    node,
                )
            )

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("_"):
            self.issues.append(
                _issue(
                    ValidationCode.DISALLOWED_ATTRIBUTE,
                    f"private attribute {node.attr!r} is not allowed",
                    node,
                )
            )
            return
        if not isinstance(node.ctx, ast.Load):
            self.issues.append(
                _issue(
                    ValidationCode.DISALLOWED_ATTRIBUTE,
                    "attribute mutation is not allowed",
                    node,
                )
            )
            return
        if isinstance(node.value, ast.Name) and node.value.id == "np":
            if node.attr not in SAFE_NUMPY_ATTRIBUTES:
                self.issues.append(
                    _issue(
                        ValidationCode.DISALLOWED_ATTRIBUTE,
                        f"numpy attribute np.{node.attr} is not allowed",
                        node,
                    )
                )
        elif node.attr not in SAFE_DATA_ATTRIBUTES:
            self.issues.append(
                _issue(
                    ValidationCode.DISALLOWED_ATTRIBUTE,
                    f"data attribute {node.attr!r} is not allowed; use mapping access instead",
                    node,
                )
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if any(keyword.arg is None for keyword in node.keywords):
            self.issues.append(
                _issue(
                    ValidationCode.DISALLOWED_CALL,
                    "expanded keyword arguments are not allowed",
                    node,
                )
            )
        if isinstance(node.func, ast.Name):
            if node.func.id not in (SAFE_BUILTIN_CALLS | self.helper_names):
                self.issues.append(
                    _issue(
                        ValidationCode.DISALLOWED_CALL,
                        f"call to {node.func.id!r} is not allowed",
                        node,
                    )
                )
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "np":
                if node.func.attr not in SAFE_NUMPY_ATTRIBUTES:
                    self.issues.append(
                        _issue(
                            ValidationCode.DISALLOWED_CALL,
                            f"call to np.{node.func.attr} is not allowed",
                            node,
                        )
                    )
            elif node.func.attr not in SAFE_METHOD_CALLS:
                self.issues.append(
                    _issue(
                        ValidationCode.DISALLOWED_CALL,
                        f"method call {node.func.attr!r} is not allowed",
                        node,
                    )
                )
        else:
            self.issues.append(
                _issue(
                    ValidationCode.DISALLOWED_CALL,
                    "indirect and dynamically computed calls are not allowed",
                    node,
                )
            )
        self.generic_visit(node)


def validate_program(source: str) -> ValidatedProgram:
    """Validate and canonicalize generated program source.

    Raises:
        SandboxValidationError: if the source is invalid or violates the
            generated-program language contract.
    """

    if not isinstance(source, str):
        raise SandboxValidationError(
            (_issue(ValidationCode.SYNTAX, "program source must be a string"),)
        )
    if len(source) > MAX_SOURCE_CHARS:
        raise SandboxValidationError(
            (
                _issue(
                    ValidationCode.SOURCE_TOO_LARGE,
                    f"program source exceeds {MAX_SOURCE_CHARS} characters",
                ),
            )
        )
    try:
        tree = ast.parse(source, filename="<generated-hypothesis>", mode="exec")
    except (SyntaxError, ValueError, TypeError, RecursionError, MemoryError) as exc:
        raise SandboxValidationError(
            (
                ValidationIssue(
                    code=ValidationCode.SYNTAX,
                    message=f"invalid Python syntax: {exc}",
                    line=getattr(exc, "lineno", None),
                    column=getattr(exc, "offset", None),
                ),
            )
        ) from exc

    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES:
        raise SandboxValidationError(
            (
                _issue(
                    ValidationCode.AST_TOO_LARGE,
                    f"program AST exceeds {MAX_AST_NODES} nodes",
                ),
            )
        )

    top_level_functions: dict[str, ast.FunctionDef] = {}
    issues: list[ValidationIssue] = []
    for statement in tree.body:
        if isinstance(statement, ast.FunctionDef):
            if statement.name in top_level_functions:
                issues.append(
                    _issue(
                        ValidationCode.INVALID_CONTRACT,
                        f"function {statement.name!r} is defined more than once",
                        statement,
                    )
                )
            top_level_functions[statement.name] = statement
        elif isinstance(statement, ast.Assign | ast.AnnAssign):
            value = statement.value
            if value is None or not _is_literal(value):
                issues.append(
                    _issue(
                        ValidationCode.INVALID_TOP_LEVEL,
                        "top-level assignments must contain literal constants only",
                        statement,
                    )
                )
        else:
            issues.append(
                _issue(
                    ValidationCode.INVALID_TOP_LEVEL,
                    "top level may contain only functions and literal constants",
                    statement,
                )
            )

    for name, required_args in _REQUIRED_SIGNATURES.items():
        function = top_level_functions.get(name)
        if function is None:
            issues.append(
                _issue(ValidationCode.INVALID_CONTRACT, f"required function {name!r} is missing")
            )
            continue
        actual_args = tuple(
            argument.arg for argument in [*function.args.posonlyargs, *function.args.args]
        )
        if actual_args != required_args or function.args.defaults:
            signature = ", ".join(required_args)
            issues.append(
                _issue(
                    ValidationCode.INVALID_CONTRACT,
                    f"{name} must have signature {name}({signature})",
                    function,
                )
            )

    helper_names = frozenset(top_level_functions)
    validator = _ProgramValidator(helper_names)
    validator.visit(tree)
    issues.extend(validator.issues)
    if issues:
        # Keep stable order while suppressing duplicate visitor/top-level reports.
        unique: list[ValidationIssue] = []
        seen: set[tuple[ValidationCode, str, int | None, int | None]] = set()
        for issue in issues:
            key = (issue.code, issue.message, issue.line, issue.column)
            if key not in seen:
                seen.add(key)
                unique.append(issue)
        raise SandboxValidationError(tuple(unique))

    canonical_source = ast.unparse(tree).strip() + "\n"
    canonical_tree = ast.parse(canonical_source, filename="<generated-hypothesis>", mode="exec")
    canonical_ast = ast.dump(canonical_tree, annotate_fields=True, include_attributes=False)
    node_count = sum(1 for _ in ast.walk(canonical_tree))
    digest = hashlib.sha256(canonical_ast.encode("utf-8")).hexdigest()
    return ValidatedProgram(
        canonical_source=canonical_source,
        canonical_ast=canonical_ast,
        node_count=node_count,
        sha256=digest,
    )


__all__ = [
    "MAX_AST_NODES",
    "MAX_SOURCE_CHARS",
    "SAFE_BUILTIN_CALLS",
    "SAFE_DATA_ATTRIBUTES",
    "SAFE_METHOD_CALLS",
    "SAFE_NUMPY_ATTRIBUTES",
    "SandboxValidationError",
    "ValidatedProgram",
    "ValidationCode",
    "ValidationIssue",
    "validate_program",
]
