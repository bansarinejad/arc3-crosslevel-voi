"""Offline diagnostics for generated-program action and palette grounding."""

from __future__ import annotations

import ast
import hashlib
import io
import re
import tokenize
from collections.abc import Sequence
from dataclasses import dataclass

from .program import ExecutableHypothesis
from .rendering import ARC_COLOR_NAMES
from .types import Action, ActionKind, History, Prediction


@dataclass(frozen=True, slots=True)
class PaletteClaim:
    line: int
    color: str
    claimed_value: int
    expected_value: int | None
    conflict: bool


@dataclass(frozen=True, slots=True)
class ActionResult:
    action: str
    ok: bool
    prediction_sha256: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ProgramGroundingResult:
    source_sha256: str
    source_length: int
    sandbox_valid: bool
    ast_nodes: int | None
    validation_error: str | None
    coordinate_read_lines: tuple[int, ...]
    palette_claims: tuple[PaletteClaim, ...]
    goal_value_ok: bool
    goal_value_error: str | None
    action_results: tuple[ActionResult, ...]
    simple_action_contract_ok: bool
    all_actions_ok: bool
    unsafe_coordinate_use: bool
    behavior_signature: str | None
    action_sensitive: bool
    hard_memory_limit_enforced: bool | None
    memory_limit_kind: str | None = None
    memory_baseline_bytes: int | None = None
    memory_ceiling_bytes: int | None = None
    memory_limit_diagnostic: str | None = None

    @property
    def palette_conflicts(self) -> tuple[PaletteClaim, ...]:
        return tuple(claim for claim in self.palette_claims if claim.conflict)

    @property
    def eligible(self) -> bool:
        return (
            self.sandbox_valid
            and self.goal_value_ok
            and self.all_actions_ok
            and not self.palette_conflicts
        )


_COLOR_EXPECTED: dict[str, int | None] = {
    name: index for index, name in enumerate(ARC_COLOR_NAMES)
}
_COLOR_EXPECTED.update(
    {
        "off white": 1,
        "off black": 4,
        "dark gray": 4,
        "neutral": 3,
        "light neutral": 2,
        "brown": None,
        "cyan": None,
        "teal": None,
    }
)
_COLOR_PATTERN = re.compile(
    r"\b(" + "|".join(
        re.escape(name) for name in sorted(_COLOR_EXPECTED, key=len, reverse=True)
    ) + r")\b",
    re.IGNORECASE,
)
_COMMENT_CLAIM_PATTERN = re.compile(
    r"\b(?P<color>"
    + "|".join(re.escape(name) for name in sorted(_COLOR_EXPECTED, key=len, reverse=True))
    + r")\b\s*(?:is|=|:|value(?:\s+is)?|val(?:\s+is)?|id(?:\s+is)?|"
    r"index(?:\s+is)?|code(?:\s+is)?)\s*(?P<value>1[0-5]|[0-9])\b",
    re.IGNORECASE,
)
_VALUE_BINDING_SUFFIXES = {"value", "val", "color", "colour", "id", "index", "code"}


def coordinate_read_lines(source: str) -> tuple[int, ...]:
    """Return source lines that read action.row or action.col."""

    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError:
        return ()
    return tuple(
        sorted(
            {
                int(node.lineno)
                for node in ast.walk(tree)
                if isinstance(node, ast.Attribute)
                and node.attr in {"row", "col"}
                and isinstance(node.value, ast.Name)
                and node.value.id == "action"
            }
        )
    )


def audit_palette_claims(source: str) -> tuple[PaletteClaim, ...]:
    """Find only explicit color-name/value claims; ignore unlabeled integers."""

    claims: dict[tuple[int, str, int], PaletteClaim] = {}
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        comments = [token for token in tokens if token.type == tokenize.COMMENT]
    except (tokenize.TokenError, IndentationError):
        comments = []
    for token in comments:
        line_number = int(token.start[0])
        _collect_comment_claims(token.string, line_number, claims)

    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError:
        return tuple(claims.values())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        target_names = {
            target.id.lower().replace("_", " ")
            for target in targets
            if isinstance(target, ast.Name)
        }
        matched_colors = {
            match.group(1).lower()
            for name in target_names
            for match in _COLOR_PATTERN.finditer(name)
        }
        if not matched_colors:
            continue
        value = node.value
        if value is None:
            continue
        integers = _assignment_claim_values(value, target_names, matched_colors)
        if len(integers) != 1:
            continue
        claimed = next(iter(integers))
        for color in matched_colors:
            _add_claim(claims, int(node.lineno), color, claimed)
    return tuple(sorted(claims.values(), key=lambda item: (item.line, item.color)))


def evaluate_program_grounding(
    source: str,
    history: History,
    actions: Sequence[Action],
    *,
    timeout_seconds: float = 0.100,
    memory_limit_mb: int = 256,
) -> ProgramGroundingResult:
    """Execute one generated program against every exposed candidate action."""

    source_sha = hashlib.sha256(source.encode("utf-8")).hexdigest()
    reads = coordinate_read_lines(source)
    claims = audit_palette_claims(source)
    try:
        hypothesis = ExecutableHypothesis(
            source,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
        )
    except Exception as exc:
        return ProgramGroundingResult(
            source_sha256=source_sha,
            source_length=len(source),
            sandbox_valid=False,
            ast_nodes=None,
            validation_error=f"{type(exc).__name__}: {exc}",
            coordinate_read_lines=reads,
            palette_claims=claims,
            goal_value_ok=False,
            goal_value_error=None,
            action_results=(),
            simple_action_contract_ok=False,
            all_actions_ok=False,
            unsafe_coordinate_use=False,
            behavior_signature=None,
            action_sensitive=False,
            hard_memory_limit_enforced=None,
        )

    memory_enforced: bool | None = None
    memory_limit_kind: str | None = None
    memory_baseline_bytes: int | None = None
    memory_ceiling_bytes: int | None = None
    memory_limit_diagnostic: str | None = None
    try:
        try:
            hypothesis.goal_value(history)
            goal_ok = True
            goal_error = None
        except Exception as exc:
            goal_ok = False
            goal_error = f"{type(exc).__name__}: {exc}"

        results: list[ActionResult] = []
        prediction_hashes: list[str] = []
        for action in actions:
            try:
                prediction = hypothesis.predict(history, action)
            except Exception as exc:
                results.append(
                    ActionResult(
                        _action_label(action),
                        False,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
                continue
            prediction_sha = _prediction_hash(prediction)
            prediction_hashes.append(prediction_sha)
            results.append(
                ActionResult(
                    _action_label(action), True, prediction_sha256=prediction_sha
                )
            )
        metadata = hypothesis.worker_metadata
        if metadata is not None:
            memory_enforced = metadata.hard_memory_limit_enforced
            memory_limit_kind = metadata.memory_limit_kind
            memory_baseline_bytes = metadata.memory_baseline_bytes
            memory_ceiling_bytes = metadata.memory_ceiling_bytes
            memory_limit_diagnostic = metadata.memory_limit_diagnostic
    finally:
        hypothesis.close()

    simple_ok = all(
        result.ok
        for action, result in zip(actions, results, strict=True)
        if action.kind is not ActionKind.ACTION6
    )
    action6_ok = any(
        result.ok
        for action, result in zip(actions, results, strict=True)
        if action.kind is ActionKind.ACTION6
    )
    all_ok = all(result.ok for result in results)
    behavior_signature = None
    if all_ok:
        behavior_signature = hashlib.sha256("|".join(prediction_hashes).encode("ascii")).hexdigest()
    return ProgramGroundingResult(
        source_sha256=source_sha,
        source_length=len(source),
        sandbox_valid=True,
        ast_nodes=hypothesis.ast_nodes,
        validation_error=None,
        coordinate_read_lines=reads,
        palette_claims=claims,
        goal_value_ok=goal_ok,
        goal_value_error=goal_error,
        action_results=tuple(results),
        simple_action_contract_ok=simple_ok,
        all_actions_ok=all_ok,
        unsafe_coordinate_use=bool(reads) and not simple_ok and action6_ok,
        behavior_signature=behavior_signature,
        action_sensitive=len(set(prediction_hashes)) > 1,
        hard_memory_limit_enforced=memory_enforced,
        memory_limit_kind=memory_limit_kind,
        memory_baseline_bytes=memory_baseline_bytes,
        memory_ceiling_bytes=memory_ceiling_bytes,
        memory_limit_diagnostic=memory_limit_diagnostic,
    )


def grounding_gate_reasons(
    programs: Sequence[ProgramGroundingResult],
    *,
    truncated_sequences: int,
    peak_vram_gb: float | None,
    tokens_per_second: float,
    max_peak_vram_gb: float = 14.5,
    min_tokens_per_second: float = 12.0,
    require_hard_memory_limit: bool = False,
) -> tuple[str, ...]:
    reasons: list[str] = []
    eligible = [program for program in programs if program.eligible]
    signatures = {
        program.behavior_signature
        for program in eligible
        if program.behavior_signature is not None
    }
    if truncated_sequences:
        reasons.append("generation truncated one or more programs")
    if len(eligible) < 2:
        reasons.append("fewer than two grounded-safe programs")
    if len(signatures) < 2:
        reasons.append("fewer than two distinct grounded behavior classes")
    if not any(program.action_sensitive for program in eligible):
        reasons.append("no grounded-safe program is action-sensitive")
    if peak_vram_gb is None or peak_vram_gb > max_peak_vram_gb:
        reasons.append("peak VRAM gate failed")
    if tokens_per_second < min_tokens_per_second:
        reasons.append("throughput gate failed")
    if require_hard_memory_limit and any(
        program.hard_memory_limit_enforced is not True for program in eligible
    ):
        reasons.append("hard sandbox memory limit was not enforced for every eligible program")
    return tuple(reasons)


def _collect_comment_claims(
    comment: str,
    line_number: int,
    claims: dict[tuple[int, str, int], PaletteClaim],
) -> None:
    for match in _COMMENT_CLAIM_PATTERN.finditer(comment):
        _add_claim(
            claims,
            line_number,
            match.group("color").lower(),
            int(match.group("value")),
        )


def _assignment_claim_values(
    value: ast.expr,
    target_names: set[str],
    matched_colors: set[str],
) -> set[int]:
    comparison_values: set[int] = set()
    for node in ast.walk(value):
        if not isinstance(node, ast.Compare):
            continue
        operands = [node.left, *node.comparators]
        for operator, left, right in zip(
            node.ops, operands[:-1], operands[1:], strict=True
        ):
            if not isinstance(operator, ast.Eq | ast.NotEq):
                continue
            claimed = _small_integer_constant(right)
            if claimed is not None and _is_grid_value_expression(left):
                comparison_values.add(claimed)
            claimed = _small_integer_constant(left)
            if claimed is not None and _is_grid_value_expression(right):
                comparison_values.add(claimed)
    if comparison_values:
        return comparison_values

    explicit_binding = any(
        name in matched_colors
        or any(
            name == f"{color} {suffix}" or name == f"{suffix} {color}"
            for color in matched_colors
            for suffix in _VALUE_BINDING_SUFFIXES
        )
        for name in target_names
    )
    if not explicit_binding:
        return set()
    claimed = _small_integer_constant(value)
    return set() if claimed is None else {claimed}


def _small_integer_constant(node: ast.AST) -> int | None:
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
        and 0 <= node.value <= 15
    ):
        return int(node.value)
    return None


def _is_grid_value_expression(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return "grid" in node.id.lower()
    if isinstance(node, ast.Subscript):
        return _is_grid_value_expression(node.value)
    return False


def _add_claim(
    claims: dict[tuple[int, str, int], PaletteClaim],
    line: int,
    color: str,
    claimed: int,
) -> None:
    expected = _COLOR_EXPECTED[color]
    claims[(line, color, claimed)] = PaletteClaim(
        line,
        color,
        claimed,
        expected,
        expected is None or expected != claimed,
    )


def _prediction_hash(prediction: Prediction) -> str:
    digest = hashlib.sha256()
    digest.update(str(tuple(prediction.next_grid.shape)).encode("ascii"))
    digest.update(prediction.next_grid.tobytes(order="C"))
    digest.update(prediction.game_state.value.encode("ascii"))
    digest.update(str(prediction.level_delta).encode("ascii"))
    return digest.hexdigest()


def _action_label(action: Action) -> str:
    if action.kind is ActionKind.ACTION6:
        return f"ACTION6({action.row},{action.col})"
    return action.kind.name
