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
from .types import Action, ActionKind, GameState, History, Observation, Prediction

# The planner maps unresolved goal value to cost as ``8 - 4 * goal_value``.
# A spread of 0.0125 is therefore the smallest admitted difference that can move
# the modeled action cost by 0.05; smaller numerical differences are not treated
# as decision-relevant graded progress.
GOAL_ACTION_SPREAD_THRESHOLD = 0.0125


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
class GoalResult:
    action: str
    depth: int
    ok: bool
    value: float | None = None
    error: str | None = None
    terminal: bool = False


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
    observed_goal_value: float | None
    goal_results: tuple[GoalResult, ...]
    goal_action_conditioned: bool
    goal_value_range: float | None
    max_action_goal_spread: float | None
    action_sensitivity_required: bool
    goal_conditioning_required: bool
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
            and (not self.action_sensitivity_required or self.action_sensitive)
            and (not self.goal_conditioning_required or self.goal_action_conditioned)
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
    rollout_depth: int = 4,
    require_action_sensitivity: bool = False,
    require_goal_conditioning: bool = False,
) -> ProgramGroundingResult:
    """Execute a program on root actions and bounded counterfactual rollouts."""

    if rollout_depth < 1:
        raise ValueError("rollout_depth must be positive")
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
            observed_goal_value=None,
            goal_results=(),
            goal_action_conditioned=False,
            goal_value_range=None,
            max_action_goal_spread=None,
            action_sensitivity_required=require_action_sensitivity,
            goal_conditioning_required=require_goal_conditioning,
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
    observed_goal_value: float | None = None
    goal_results: list[GoalResult] = []
    try:
        try:
            observed_goal_value = hypothesis.goal_value(history)
            observed_goal_ok = True
            goal_error = None
        except Exception as exc:
            observed_goal_ok = False
            goal_error = f"{type(exc).__name__}: {exc}"

        results: list[ActionResult] = []
        prediction_hashes: list[str] = []
        root_predictions: list[Prediction | None] = []
        for action in actions:
            try:
                prediction = hypothesis.predict(history, action)
            except Exception as exc:
                root_predictions.append(None)
                results.append(
                    ActionResult(
                        _action_label(action),
                        False,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
                continue
            root_predictions.append(prediction)
            prediction_sha = _prediction_hash(prediction)
            prediction_hashes.append(prediction_sha)
            results.append(
                ActionResult(
                    _action_label(action), True, prediction_sha256=prediction_sha
                )
            )

        available_actions = frozenset(action.kind for action in actions)
        for action, root_prediction in zip(actions, root_predictions, strict=True):
            if root_prediction is None:
                continue
            rollout_history = history
            prediction = root_prediction
            for depth in range(1, rollout_depth + 1):
                if depth > 1:
                    try:
                        prediction = hypothesis.predict(rollout_history, action)
                    except Exception as exc:
                        goal_results.append(
                            GoalResult(
                                _action_label(action),
                                depth,
                                False,
                                error=f"predict: {type(exc).__name__}: {exc}",
                            )
                        )
                        break
                if _terminal_prediction(prediction):
                    goal_results.append(
                        GoalResult(
                            _action_label(action),
                            depth,
                            True,
                            terminal=True,
                        )
                    )
                    break
                rollout_history = _advance_history(
                    rollout_history,
                    action,
                    prediction,
                    available_actions,
                )
                try:
                    value = hypothesis.goal_value(rollout_history)
                except Exception as exc:
                    goal_results.append(
                        GoalResult(
                            _action_label(action),
                            depth,
                            False,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    )
                    break
                goal_results.append(
                    GoalResult(_action_label(action), depth, True, value=value)
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

    goal_values = [
        value
        for value in (
            observed_goal_value,
            *(result.value for result in goal_results if result.ok),
        )
        if value is not None
    ]
    goal_range = max(goal_values) - min(goal_values) if goal_values else None
    depth_spreads = [
        max(values) - min(values)
        for depth in range(1, rollout_depth + 1)
        if len(
            values := [
                result.value
                for result in goal_results
                if result.ok and result.depth == depth and result.value is not None
            ]
        )
        >= 2
    ]
    max_action_goal_spread = max(depth_spreads) if depth_spreads else None
    goal_action_conditioned = (
        max_action_goal_spread is not None
        and max_action_goal_spread >= GOAL_ACTION_SPREAD_THRESHOLD
    )
    goal_ok = (
        observed_goal_ok
        and all(result.ok for result in goal_results)
    )
    if observed_goal_ok and not goal_ok and goal_error is None:
        goal_error = "one or more counterfactual goal rollouts failed"
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
        observed_goal_value=observed_goal_value,
        goal_results=tuple(goal_results),
        goal_action_conditioned=goal_action_conditioned,
        goal_value_range=goal_range,
        max_action_goal_spread=max_action_goal_spread,
        action_sensitivity_required=require_action_sensitivity,
        goal_conditioning_required=require_goal_conditioning,
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
    """Return fail-closed reasons for the offline model-generation smoke diagnostic.

    This two-graded-role diagnostic is deliberately stricter than live runtime
    admission. It demonstrates that a candidate model/configuration can generate a
    minimally useful committee before an expensive gameplay pilot; it does not alter
    the controller's general runtime semantics.
    """

    reasons: list[str] = []
    eligible = [program for program in programs if program.eligible]
    eligible_graded_roles = [
        program
        for program in eligible
        if program.action_sensitivity_required
        and program.goal_conditioning_required
    ]
    signatures = {
        program.behavior_signature
        for program in eligible
        if program.behavior_signature is not None
    }
    if truncated_sequences:
        reasons.append("generation truncated one or more programs")
    if len(eligible) < 2:
        reasons.append("fewer than two grounded-safe programs")
    if len(eligible_graded_roles) < 2:
        reasons.append("fewer than two eligible graded-role programs")
    if len(signatures) < 2:
        reasons.append("fewer than two distinct grounded behavior classes")
    if not any(program.action_sensitive for program in eligible):
        reasons.append("no grounded-safe program is action-sensitive")
    if not any(program.goal_action_conditioned for program in eligible):
        reasons.append(
            "no grounded-safe program has action-conditioned counterfactual goal variation"
        )
    if peak_vram_gb is None or peak_vram_gb > max_peak_vram_gb:
        reasons.append("peak VRAM gate failed")
    if tokens_per_second < min_tokens_per_second:
        reasons.append("throughput gate failed")
    if require_hard_memory_limit and any(
        program.hard_memory_limit_enforced is not True for program in eligible
    ):
        reasons.append("hard sandbox memory limit was not enforced for every eligible program")
    return tuple(reasons)


def _advance_history(
    history: History,
    action: Action,
    prediction: Prediction,
    available_actions: frozenset[ActionKind],
) -> History:
    level = max(1, history.current_level + max(0, prediction.level_delta))
    observation = Observation(
        prediction.next_grid,
        available_actions,
        prediction.game_state,
        level=level,
        win_levels=level,
    )
    return history.append(observation, action, prediction.level_delta)


def _terminal_prediction(prediction: Prediction) -> bool:
    return (
        prediction.level_delta > 0
        or prediction.game_state is GameState.WIN
        or prediction.game_state is GameState.GAME_OVER
    )


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
