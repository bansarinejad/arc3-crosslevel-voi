from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from arc3_voi.action_qbc_policy import (
    ACTION_QBC_POLICY_SHA256,
    ACTION_QBC_POLICY_VERSION,
    ACTION_QBC_RUNTIME_VERSION,
    OUTCOME_CONCENTRATION_THRESHOLD,
)
from arc3_voi.controller import Variant
from arc3_voi.metrics import RunMetrics, load_run, write_run
from arc3_voi.planner import (
    COMPLETION_COST_POLICY_HASHES,
    PATH_DEFICIT_COMPLETION_COST_POLICY,
)
from arc3_voi.run_store import (
    TRACE_ARTIFACT_KEY,
    V5_POLICY_IDENTITY_KEYS,
    V5_REGISTERED_CONFIG_SHA256_BY_ARM,
    read_complete_run,
    validate_action_qbc_attribution,
    validate_action_qbc_candidate_rows,
    validate_v5_policy_identity,
)
from arc3_voi.runner import run_game
from arc3_voi.types import (
    Action,
    ActionKind,
    Decision,
    DecisionMode,
    GameState,
    Observation,
)

from .test_controller_v5 import _controller, _observation
from .test_runner import FakeSession


def _identity(*, threshold: float = OUTCOME_CONCENTRATION_THRESHOLD) -> dict[str, Any]:
    return {
        "implementation_contract_version": ACTION_QBC_RUNTIME_VERSION,
        "completion_cost_policy_version": PATH_DEFICIT_COMPLETION_COST_POLICY,
        "completion_cost_policy_sha256": COMPLETION_COST_POLICY_HASHES[
            PATH_DEFICIT_COMPLETION_COST_POLICY
        ],
        "probe_disagreement_policy_version": ACTION_QBC_POLICY_VERSION,
        "probe_disagreement_policy_sha256": ACTION_QBC_POLICY_SHA256,
        "outcome_concentration_threshold": threshold,
    }


def _candidate_rows() -> list[dict[str, Any]]:
    shared = {
        "outcome_concentration": 0.5,
        "outcome_cell_count": 2,
        "evsi": 0.25,
        "catastrophe_mass": 0.0,
        "m_utility": -0.75,
        "x_utility": 4.75,
        "eligible": True,
        "exploit_mean_cost": 2.0,
        "exploit_standard_deviation": 1.0,
        "exploit_score": 2.5,
    }
    return [
        {
            **shared,
            "action": {"kind": "ACTION1", "row": None, "col": None},
            "m_rank": 1,
            "x_rank": 1,
            "m_selected": False,
            "x_selected": False,
        },
        {
            **shared,
            "action": {"kind": "ACTION2", "row": None, "col": None},
            "m_rank": 2,
            "x_rank": 2,
            "m_selected": False,
            "x_selected": False,
        },
    ]


class AttributedController:
    pool = None

    def __init__(
        self,
        *,
        mode: DecisionMode = DecisionMode.EXPLOIT,
        identity: dict[str, Any] | None = None,
        include_rows: bool = True,
        post_refresh_mode: str | None = None,
        rows_json: object | None = None,
        paired_x_probe: bool = False,
    ) -> None:
        self.mode = mode
        self.identity = _identity() if identity is None else identity
        self.include_rows = include_rows
        self.post_refresh_mode = post_refresh_mode
        self.rows_json = rows_json
        self.paired_x_probe = paired_x_probe
        self.authoritative_variant = "X"

    def act(self, observation: Observation, budget: object) -> Decision:
        del observation, budget
        diagnostics: dict[str, Any] = {**self.identity, "generated_tokens": 0}
        score = 0.0
        strategy_mode = (
            self.post_refresh_mode
            if self.mode is DecisionMode.REFRESH
            else self.mode.value
        )
        if self.include_rows:
            rows = _candidate_rows()
            if self.paired_x_probe or strategy_mode == DecisionMode.PROBE.value:
                rows[0]["x_selected"] = True
            probe_count_before = (
                0
                if self.paired_x_probe or strategy_mode == DecisionMode.PROBE.value
                else 3
            )
            x_mode = "probe" if rows[0]["x_selected"] else "exploit"
            diagnostics["action_qbc_candidate_rows"] = (
                json.dumps(rows, separators=(",", ":"))
                if self.rows_json is None
                else self.rows_json
            )
            diagnostics.update(
                {
                    "m_decision_action": "ACTION1",
                    "m_decision_mode": "exploit",
                    "x_decision_action": "ACTION1",
                    "x_decision_mode": x_mode,
                    "m_level_multiplier": 1.0,
                    "x_level_multiplier": 23.0,
                    "level_multiplier": (
                        1.0 if self.authoritative_variant == "M" else 23.0
                    ),
                    "m_utility_maximizer_actions": json.dumps(
                        [row["action"] for row in rows], separators=(",", ":")
                    ),
                    "x_utility_maximizer_actions": json.dumps(
                        [row["action"] for row in rows], separators=(",", ":")
                    ),
                    "probe_cap": 3,
                    "probe_count_before": probe_count_before,
                    "probe_count_after": probe_count_before
                    + int(
                        self.authoritative_variant == "X" and x_mode == "probe"
                    ),
                    "probe_candidate_action": "ACTION1",
                    "probe_evsi": rows[0]["evsi"],
                    "probe_catastrophe_probability": rows[0]["catastrophe_mass"],
                    "probe_utility": rows[0][
                        "m_utility"
                        if self.authoritative_variant == "M"
                        else "x_utility"
                    ],
                    "probe_gate_reason": (
                        "nonpositive_utility"
                        if self.authoritative_variant == "M"
                        else (
                            "selected"
                            if x_mode == "probe"
                            else "level_probe_cap_reached"
                        )
                    ),
                    "probe_selected": (
                        self.authoritative_variant == "X" and x_mode == "probe"
                    ),
                }
            )
            authoritative_probe = (
                self.authoritative_variant == "X" and x_mode == "probe"
            )
            score = float(
                rows[0]["x_utility"]
                if authoritative_probe
                else rows[0]["exploit_score"]
            )
        if self.post_refresh_mode is not None:
            diagnostics["post_refresh_mode"] = self.post_refresh_mode
        return Decision(Action(ActionKind.ACTION1), self.mode, score, diagnostics)


def _run(
    controller: AttributedController,
    *,
    variant: str = "X",
    identity: dict[str, Any] | None = None,
    run_id: str = "v5-attribution",
    config_hash: str = "v5-config",
) -> RunMetrics:
    controller.authoritative_variant = variant
    return run_game(
        FakeSession(),
        controller,
        run_id=run_id,
        seed=1,
        variant=variant,
        model_profile="test",
        config_hash=config_hash,
        hypothesis_source="qwen",
        arm_label=f"{variant}-Q",
        identity_version="legacy-v1",
        producer_contract_sha256=None,
        **(_identity() if identity is None else identity),
    )


def test_v5_identity_and_structured_rows_round_trip(tmp_path: Path) -> None:
    metrics = _run(AttributedController())

    assert metrics.error is None
    assert all(
        getattr(metrics, key) == _identity()[key] for key in V5_POLICY_IDENTITY_KEYS
    )
    assert all(step.action_qbc_candidate_rows for step in metrics.steps)
    assert all(
        isinstance(step.action_qbc_candidate_rows, tuple) for step in metrics.steps
    )
    assert all(step.post_refresh_mode is None for step in metrics.steps)
    assert all(
        getattr(step, key) == getattr(metrics, key)
        for step in metrics.steps
        for key in V5_POLICY_IDENTITY_KEYS
    )

    summary, trace = write_run(metrics, tmp_path)
    raw_row = json.loads(trace.read_text(encoding="utf-8").splitlines()[0])
    assert isinstance(raw_row["action_qbc_candidate_rows"], list)
    assert raw_row["post_refresh_mode"] is None
    restored = load_run(summary, trace)
    assert restored.summary() == metrics.summary()
    assert [step.action_qbc_candidate_rows for step in restored.steps] == [
        step.action_qbc_candidate_rows for step in metrics.steps
    ]
    assert all(
        getattr(step, key) == getattr(metrics, key)
        for step in restored.steps
        for key in V5_POLICY_IDENTITY_KEYS
    )


def test_v5_refresh_records_explicit_post_refresh_mode() -> None:
    metrics = _run(
        AttributedController(
            mode=DecisionMode.REFRESH,
            post_refresh_mode=DecisionMode.PROBE.value,
        )
    )

    assert metrics.error is None
    assert all(step.post_refresh_mode == "probe" for step in metrics.steps)


@pytest.mark.parametrize("variant", ("D", "S"))
def test_v5_noncommittee_rows_never_carry_candidate_table(variant: str) -> None:
    metrics = _run(
        AttributedController(include_rows=False),
        variant=variant,
        run_id=f"v5-{variant.lower()}",
    )

    assert metrics.error is None
    assert all(step.action_qbc_candidate_rows is None for step in metrics.steps)


def test_v5_direct_fallback_never_carries_candidate_table() -> None:
    metrics = _run(
        AttributedController(mode=DecisionMode.DIRECT_FALLBACK, include_rows=False)
    )

    assert metrics.error is None
    assert all(step.action_qbc_candidate_rows is None for step in metrics.steps)


def test_runner_fails_closed_on_summary_decision_identity_mismatch() -> None:
    diagnostics_identity = _identity(threshold=0.7)
    metrics = _run(AttributedController(identity=diagnostics_identity))

    assert metrics.total_actions == 0
    assert metrics.error is not None
    assert "exact registered runtime-v5 tuple" in metrics.error


def test_runner_fails_closed_on_incomplete_decision_identity() -> None:
    metrics = _run(
        AttributedController(
            identity={"implementation_contract_version": ACTION_QBC_RUNTIME_VERSION},
            include_rows=False,
        )
    )

    assert metrics.total_actions == 0
    assert metrics.error is not None
    assert "incomplete runtime-v5 identity" in metrics.error


@pytest.mark.parametrize("rows_json", ("not-json", "[]", '{"not":"rows"}'))
def test_runner_rejects_malformed_or_empty_candidate_rows(rows_json: str) -> None:
    metrics = _run(AttributedController(rows_json=rows_json))

    assert metrics.total_actions == 0
    assert metrics.error is not None
    assert "candidate row" in metrics.error or "candidate rows" in metrics.error


def test_runner_rejects_candidate_rows_outside_successful_mx_planning() -> None:
    metrics = _run(AttributedController(), variant="D", run_id="v5-d-with-rows")

    assert metrics.total_actions == 0
    assert metrics.error is not None
    assert "valid only for successful M/X planning" in metrics.error


def test_exploit_arm_may_have_no_probe_selected_candidate_row() -> None:
    rows = _candidate_rows()
    metrics = _run(
        AttributedController(rows_json=json.dumps(rows, separators=(",", ":")))
    )

    assert metrics.error is None
    assert all(
        not any(row["m_selected"] for row in (step.action_qbc_candidate_rows or ()))
        for step in metrics.steps
    )


@pytest.mark.parametrize("later_score", (3.5, 2.5))
def test_attribution_rejects_higher_score_or_tied_later_exploit_action(
    later_score: float,
) -> None:
    rows = _candidate_rows()
    rows[1]["exploit_mean_cost"] = later_score - 0.5
    rows[1]["exploit_score"] = later_score
    diagnostics = {
        **_identity(),
        "action_qbc_candidate_rows": json.dumps(rows, separators=(",", ":")),
        "m_decision_action": "ACTION2",
        "m_decision_mode": "exploit",
        "x_decision_action": "ACTION2",
        "x_decision_mode": "exploit",
        "m_level_multiplier": 1.0,
        "x_level_multiplier": 23.0,
        "level_multiplier": 23.0,
        "m_utility_maximizer_actions": json.dumps(
            [row["action"] for row in rows], separators=(",", ":")
        ),
        "x_utility_maximizer_actions": json.dumps(
            [row["action"] for row in rows], separators=(",", ":")
        ),
        "probe_cap": 3,
        "probe_count_before": 3,
        "probe_count_after": 3,
        "probe_candidate_action": "ACTION1",
        "probe_evsi": rows[0]["evsi"],
        "probe_catastrophe_probability": rows[0]["catastrophe_mass"],
        "probe_utility": rows[0]["x_utility"],
        "probe_gate_reason": "level_probe_cap_reached",
        "probe_selected": False,
    }

    with pytest.raises(ValueError, match="decision disagrees with its gate inputs"):
        validate_action_qbc_attribution(
            rows,
            variant="X",
            decision_mode="exploit",
            decision_score=later_score,
            post_refresh_mode=None,
            action={"kind": "ACTION2"},
            decision_diagnostics=diagnostics,
            context="tampered attribution",
        )


def test_real_v5_controller_diagnostics_flow_into_structured_trace() -> None:
    class OneStepSession:
        game_id = "open-v5-integration"

        def initial_observation(self) -> Observation:
            return _observation()

        def step(self, action: Action, *, reasoning: object = None) -> Observation:
            del action, reasoning
            return Observation(
                np.zeros((2, 2), dtype=np.int16),
                frozenset(
                    {ActionKind.ACTION1, ActionKind.ACTION2, ActionKind.ACTION3}
                ),
                GameState.WIN,
                level=9,
                win_levels=9,
            )

    metrics = run_game(
        OneStepSession(),
        _controller(Variant.CROSS_LEVEL),
        run_id="real-v5-attribution",
        seed=1,
        variant="X",
        model_profile="open-fixture",
        config_hash="v5-config",
        hypothesis_source="qwen",
        arm_label="X-Q",
        identity_version="legacy-v1",
        producer_contract_sha256=None,
        **_identity(),
    )

    assert metrics.error is None
    assert metrics.steps[0].decision_mode == "probe"
    rows = metrics.steps[0].action_qbc_candidate_rows
    assert rows is not None
    assert [row["action"]["kind"] for row in rows] == [
        "ACTION1",
        "ACTION2",
        "ACTION3",
    ]
    assert [row["m_selected"] for row in rows] == [False, False, False]
    assert [row["x_selected"] for row in rows] == [False, False, True]


@pytest.mark.parametrize(
    ("mode", "post_refresh_mode"),
    (
        (DecisionMode.REFRESH, None),
        (DecisionMode.EXPLOIT, DecisionMode.PROBE.value),
    ),
)
def test_runner_requires_post_refresh_mode_exactly_for_refresh(
    mode: DecisionMode, post_refresh_mode: str | None
) -> None:
    metrics = _run(
        AttributedController(mode=mode, post_refresh_mode=post_refresh_mode)
    )

    assert metrics.total_actions == 0
    assert metrics.error is not None
    assert "post_refresh_mode" in metrics.error


def test_run_metrics_rejects_incomplete_v5_identity() -> None:
    with pytest.raises(ValueError, match="incomplete runtime-v5 identity"):
        RunMetrics(
            "incomplete-v5",
            "game",
            1,
            "X",
            "test",
            "config",
            hypothesis_source="qwen",
            arm_label="X-Q",
            identity_version="legacy-v1",
            producer_contract_sha256=None,
            implementation_contract_version=ACTION_QBC_RUNTIME_VERSION,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("implementation_contract_version", "crosslevel-voi-runtime-v5-drift"),
        ("completion_cost_policy_version", "endpoint-v1"),
        ("completion_cost_policy_sha256", "0" * 64),
        ("probe_disagreement_policy_version", "winning-action-agreement-v1"),
        ("probe_disagreement_policy_sha256", "0" * 64),
        ("outcome_concentration_threshold", 0.7),
    ),
)
def test_v5_identity_requires_every_exact_registered_value(
    field: str, value: object
) -> None:
    identity = _identity()
    identity[field] = value

    with pytest.raises(ValueError, match=rf"{field}.*exact registered runtime-v5"):
        validate_v5_policy_identity(identity, context="test identity")


@pytest.mark.parametrize(
    "mutation",
    (
        "missing_field",
        "nonfinite",
        "out_of_range",
        "eligibility_relation",
        "eligible_null_rank",
        "ineligible_nonnull_rank",
        "duplicate_rank",
        "rank_utility_order",
        "selected_ineligible",
        "multiple_selected",
        "too_many_cells",
    ),
)
def test_shared_candidate_validator_rejects_schema_and_semantic_drift(
    mutation: str,
) -> None:
    rows = _candidate_rows()
    if mutation == "missing_field":
        rows[0].pop("evsi")
    elif mutation == "nonfinite":
        rows[0]["evsi"] = float("nan")
    elif mutation == "out_of_range":
        rows[0]["catastrophe_mass"] = 1.1
    elif mutation == "eligibility_relation":
        rows[0]["outcome_concentration"] = 0.9
    elif mutation == "eligible_null_rank":
        rows[0]["m_rank"] = None
    elif mutation == "ineligible_nonnull_rank":
        rows[0].update(
            {
                "outcome_concentration": 0.9,
                "eligible": False,
                "x_rank": None,
            }
        )
    elif mutation == "duplicate_rank":
        rows[1]["m_rank"] = 1
    elif mutation == "rank_utility_order":
        rows[0]["m_utility"] = -0.5
        rows[1]["m_utility"] = 0.5
    elif mutation == "selected_ineligible":
        rows[0].update(
            {
                "outcome_concentration": 0.9,
                "eligible": False,
                "m_rank": None,
                "x_rank": None,
                "m_selected": True,
            }
        )
    elif mutation == "multiple_selected":
        rows[0]["x_selected"] = True
        rows[1]["x_selected"] = True
    elif mutation == "too_many_cells":
        rows[0]["outcome_cell_count"] = 5
    else:  # pragma: no cover - parametrization is exhaustive
        raise AssertionError(mutation)

    with pytest.raises(ValueError):
        validate_action_qbc_candidate_rows(rows, context="test rows")


def test_step_record_direct_construction_uses_shared_candidate_validator() -> None:
    metrics = _run(AttributedController())
    assert metrics.error is None
    rows = [dict(row) for row in metrics.steps[0].action_qbc_candidate_rows or ()]
    rows[0].pop("evsi")

    with pytest.raises(ValueError, match="invalid schema"):
        replace(metrics.steps[0], action_qbc_candidate_rows=tuple(rows))


def test_historical_step_cannot_silently_carry_v5_only_attribution() -> None:
    metrics = _run(AttributedController())
    assert metrics.error is None

    with pytest.raises(ValueError, match="require a runtime-v5 step identity"):
        replace(
            metrics.steps[0],
            implementation_contract_version=None,
            completion_cost_policy_version=None,
            completion_cost_policy_sha256=None,
            probe_disagreement_policy_version=None,
            probe_disagreement_policy_sha256=None,
            outcome_concentration_threshold=None,
        )


def test_publication_rejects_contextually_false_selected_flag(tmp_path: Path) -> None:
    metrics = _run(AttributedController())
    assert metrics.error is None
    rows = [dict(row) for row in metrics.steps[0].action_qbc_candidate_rows or ()]
    rows[0]["x_selected"] = True
    metrics.steps[0] = replace(
        metrics.steps[0], action_qbc_candidate_rows=tuple(rows)
    )

    with pytest.raises(ValueError, match="complete and consistent"):
        write_run(metrics, tmp_path)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("probe_count_after", 4),
        ("probe_gate_reason", "selected"),
        ("probe_evsi", 0.5),
        ("x_utility_maximizer_actions", "[]"),
        ("level_multiplier", 1.0),
    ),
)
def test_publication_rejects_forged_probe_headline_or_accounting(
    field: str,
    value: object,
    tmp_path: Path,
) -> None:
    metrics = _run(AttributedController())
    assert metrics.error is None
    diagnostics = dict(metrics.steps[0].decision_diagnostics)
    diagnostics[field] = value
    metrics.steps[0] = replace(
        metrics.steps[0], decision_diagnostics=diagnostics
    )

    with pytest.raises(ValueError, match="complete and consistent"):
        write_run(metrics, tmp_path)


def test_publication_rejects_forged_authoritative_decision_score(
    tmp_path: Path,
) -> None:
    metrics = _run(AttributedController())
    assert metrics.error is None
    metrics.steps[0] = replace(metrics.steps[0], decision_score=3.0)

    with pytest.raises(ValueError, match="complete and consistent"):
        write_run(metrics, tmp_path)


def test_paired_other_variant_probe_selection_is_preserved() -> None:
    metrics = _run(
        AttributedController(paired_x_probe=True),
        variant="M",
        run_id="v5-m-with-paired-x-probe",
    )

    assert metrics.error is None
    for step in metrics.steps:
        rows = step.action_qbc_candidate_rows
        assert rows is not None
        assert [row["m_selected"] for row in rows] == [False, False]
        assert [row["x_selected"] for row in rows] == [True, False]


def test_authoritative_probe_flag_must_match_action() -> None:
    rows = _candidate_rows()
    rows[0]["m_rank"] = 2
    rows[0]["x_rank"] = 2
    rows[1]["evsi"] = 0.3
    rows[1]["m_utility"] = 0.3 - 1.0
    rows[1]["x_utility"] = 23.0 * 0.3 - 1.0
    rows[1]["m_rank"] = 1
    rows[1]["x_rank"] = 1
    rows[1]["x_selected"] = True
    metrics = _run(
        AttributedController(
            mode=DecisionMode.PROBE,
            rows_json=json.dumps(rows, separators=(",", ":")),
        )
    )

    assert metrics.total_actions == 0
    assert metrics.error is not None
    assert "paired X decision disagrees with its gate inputs" in metrics.error


def test_v5_summary_trace_identity_mismatch_is_rejected(tmp_path: Path) -> None:
    summary, trace = write_run(_run(AttributedController()), tmp_path)
    summary_payload = json.loads(summary.read_text(encoding="utf-8"))
    summary_payload.pop(TRACE_ARTIFACT_KEY)
    summary.write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    rows = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    rows[0]["outcome_concentration_threshold"] = 0.7
    trace.write_text(
        "".join(
            json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(ValueError, match="incomplete or inconsistent"):
        load_run(summary, trace)


def test_registered_v5_config_cannot_be_checksum_downgraded_to_historical(
    tmp_path: Path,
) -> None:
    summary, trace = write_run(
        _run(
            AttributedController(),
            config_hash=V5_REGISTERED_CONFIG_SHA256_BY_ARM["X-T"],
        ),
        tmp_path,
    )
    summary_payload = json.loads(summary.read_text(encoding="utf-8"))
    trace_rows = [
        json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()
    ]
    for key in V5_POLICY_IDENTITY_KEYS:
        summary_payload.pop(key)
    for row in trace_rows:
        for key in (*V5_POLICY_IDENTITY_KEYS, "action_qbc_candidate_rows", "post_refresh_mode"):
            row.pop(key)
        diagnostics = row["decision_diagnostics"]
        for key in (
            *V5_POLICY_IDENTITY_KEYS,
            "action_qbc_candidate_rows",
            "m_decision_action",
            "m_decision_mode",
            "x_decision_action",
            "x_decision_mode",
            "m_level_multiplier",
            "x_level_multiplier",
        ):
            diagnostics.pop(key, None)
    trace_bytes = "".join(
        json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n"
        for row in trace_rows
    ).encode("utf-8")
    trace.write_bytes(trace_bytes)
    summary_payload[TRACE_ARTIFACT_KEY]["sha256"] = hashlib.sha256(
        trace_bytes
    ).hexdigest()
    summary.write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    assert read_complete_run(summary, trace) is None
    with pytest.raises(ValueError, match="incomplete or inconsistent"):
        load_run(summary, trace)


def test_registered_v5_config_requires_policy_identity_at_construction() -> None:
    with pytest.raises(ValueError, match="registered runtime-v5 config hash"):
        RunMetrics(
            "downgraded-v5",
            "game",
            1,
            "X",
            "test",
            V5_REGISTERED_CONFIG_SHA256_BY_ARM["X-T"],
            hypothesis_source="template_v1",
            arm_label="X-T",
            identity_version="source-v2",
            producer_contract_sha256="a" * 64,
        )


def test_retry_identity_includes_complete_v5_policy_tuple(tmp_path: Path) -> None:
    first = RunMetrics(
        "v5-retry",
        "game",
        1,
        "X",
        "test",
        "config",
        hypothesis_source="qwen",
        arm_label="X-Q",
        identity_version="legacy-v1",
        producer_contract_sha256=None,
        error="failed",
        **_identity(),
    )
    write_run(first, tmp_path)
    summary_path = tmp_path / "v5-retry.json"
    tampered = json.loads(summary_path.read_text(encoding="utf-8"))
    tampered["outcome_concentration_threshold"] = 0.7
    summary_path.write_text(
        json.dumps(tampered, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    changed = RunMetrics(
        "v5-retry",
        "game",
        1,
        "X",
        "test",
        "config",
        hypothesis_source="qwen",
        arm_label="X-Q",
        identity_version="legacy-v1",
        producer_contract_sha256=None,
        error="failed again",
        **_identity(),
    )

    with pytest.raises(FileExistsError, match="outcome_concentration_threshold"):
        write_run(changed, tmp_path)

    historical_retry = RunMetrics(
        "v5-retry",
        "game",
        1,
        "X",
        "test",
        "config",
        hypothesis_source="qwen",
        arm_label="X-Q",
        identity_version="legacy-v1",
        producer_contract_sha256=None,
        error="historical retry",
    )
    with pytest.raises(FileExistsError, match="implementation_contract_version"):
        write_run(historical_retry, tmp_path)


def test_historical_summary_and_trace_omit_v5_fields(tmp_path: Path) -> None:
    historical = RunMetrics(
        "historical",
        "game",
        1,
        "D",
        "test",
        "config",
        hypothesis_source="qwen",
        arm_label="D-Q",
        identity_version="legacy-v1",
        producer_contract_sha256=None,
    )
    assert not set(V5_POLICY_IDENTITY_KEYS).intersection(historical.summary())

    metrics = run_game(
        FakeSession(),
        AttributedController(identity={}, include_rows=False),
        run_id="historical-trace",
        seed=1,
        variant="D",
        model_profile="test",
        config_hash="historical-config",
        hypothesis_source="qwen",
        arm_label="D-Q",
        identity_version="legacy-v1",
        producer_contract_sha256=None,
    )
    summary, trace = write_run(metrics, tmp_path)
    assert not set(V5_POLICY_IDENTITY_KEYS).intersection(
        json.loads(summary.read_text(encoding="utf-8"))
    )
    raw_row = json.loads(trace.read_text(encoding="utf-8").splitlines()[0])
    assert not set(V5_POLICY_IDENTITY_KEYS).intersection(raw_row)
    assert "action_qbc_candidate_rows" not in raw_row
    assert "post_refresh_mode" not in raw_row
