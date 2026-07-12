from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from arc3_voi.prompts import (
    DIRECT_SYSTEM_PROMPT,
    PROGRAM_SYSTEM_PROMPT,
    PROMPT_CONTRACT_SHA256,
    PROMPT_REFERENCE_DIRECT_SHA256,
    PROMPT_REFERENCE_PROGRAM_SHA256,
    extract_python,
    history_payload,
    parse_action_json,
    program_prompt,
)
from arc3_voi.rendering import ARC_PALETTE_LEGEND


def test_extract_python_fence() -> None:
    assert extract_python("```python\ndef predict():\n    pass\n```") == "def predict():\n    pass"


def test_extract_python_discards_thinking_and_leading_prose() -> None:
    text = "<think>reasoning</think>Here is code:\ndef predict(history, action):\n    return {}"
    assert extract_python(text).startswith("def predict(history, action):")


def test_extract_python_prefers_complete_fenced_program() -> None:
    text = (
        "```python\ndef helper():\n    pass\n```\n```python\n"
        "def predict(history, action):\n    return {}\n"
        "def goal_value(history):\n    return 0\n```"
    )
    extracted = extract_python(text)
    assert extracted.startswith("def predict")
    assert "def goal_value" in extracted


def test_extract_python_handles_unclosed_fence() -> None:
    text = (
        "```python\ndef predict(history, action):\n    return {}\n"
        "def goal_value(history):\n    return 0\n```"
    )
    assert not extract_python(text).endswith("```")


def test_parse_action_json_with_surrounding_text() -> None:
    assert parse_action_json('choice: {"kind":"ACTION1"}') == {"kind": "ACTION1"}


def test_parse_action_json_rejects_missing_kind() -> None:
    with pytest.raises(ValueError):
        parse_action_json('{"row":1}')


def test_history_payload_is_compact_and_stable() -> None:
    entry = SimpleNamespace(
        grid=np.zeros((64, 64), dtype=np.int8),
        action=SimpleNamespace(kind="ACTION6", row=2, col=3),
        available_actions=("ACTION1", "ACTION6"),
        game_state="NOT_FINISHED",
        level_delta=0,
        level=1,
    )
    payload = history_payload([entry])
    assert payload[0]["action"] == {"kind": "ACTION6", "row": 2, "col": 3}
    assert len(payload[0]["grid"].splitlines()) == 64


def test_history_payload_sorts_available_actions_by_contract_id() -> None:
    entry = SimpleNamespace(
        grid=np.zeros((2, 2), dtype=np.int8),
        action=None,
        available_actions=("ACTION7", "ACTION3", "RESET", "ACTION6"),
        game_state="NOT_FINISHED",
        level_delta=0,
        level=1,
    )

    payload = history_payload([entry])

    assert payload[0]["available_actions"] == [
        "RESET",
        "ACTION3",
        "ACTION6",
        "ACTION7",
    ]


def test_image_backed_history_payload_preserves_eight_aligned_frames() -> None:
    entries = [
        SimpleNamespace(
            grid=np.full((64, 64), index % 10, dtype=np.int8),
            action=None if index == 0 else SimpleNamespace(kind="ACTION1"),
            available_actions=("ACTION1", "ACTION6"),
            game_state="NOT_FINISHED",
            level_delta=index % 2,
            level=1 + index // 5,
        )
        for index in range(10)
    ]

    payload = history_payload(entries, include_grid_ascii=False)

    assert len(payload) == 8
    assert [entry["grid_image_index"] for entry in payload] == list(range(8))
    assert all("grid" not in entry for entry in payload)
    assert payload[0]["level_delta"] == 0  # Original entry 2.
    assert payload[-1]["level"] == 2
    assert payload[-1]["action"] == {"kind": "ACTION1"}
    assert payload[-1]["grid_values"] == [9]


def test_prompts_share_exact_palette_and_action_contracts() -> None:
    assert ARC_PALETTE_LEGEND in PROGRAM_SYSTEM_PROMPT
    assert ARC_PALETTE_LEGEND in DIRECT_SYSTEM_PROMPT
    assert "Only ACTION6 carries coordinates" in PROGRAM_SYSTEM_PROMPT
    assert "For every other kind, row and col are None" in PROGRAM_SYSTEM_PROMPT
    assert "copy one exact" in DIRECT_SYSTEM_PROMPT.lower()
    assert "Return one listed" in DIRECT_SYSTEM_PROMPT
    assert len(PROMPT_CONTRACT_SHA256) == 64
    int(PROMPT_CONTRACT_SHA256, 16)
    assert len(PROMPT_REFERENCE_PROGRAM_SHA256) == 64
    assert len(PROMPT_REFERENCE_DIRECT_SHA256) == 64


def test_program_prompt_assigns_distinct_action_sensitive_committee_roles() -> None:
    entry = SimpleNamespace(
        grid=np.zeros((64, 64), dtype=np.int8),
        action=None,
        available_actions=("ACTION7", "ACTION3", "ACTION6"),
        game_state="NOT_FINISHED",
        level_delta=0,
        level=1,
    )

    prompts = [
        program_prompt([entry], candidate_index=index, candidate_count=4)
        for index in range(4)
    ]

    assert len(set(prompts)) == 4
    assert "no-effect transition is acceptable" in prompts[0]
    assert all("Predictions should differ" in prompt for prompt in prompts[1:])
    assert '"index":0' in prompts[0]
    assert '"index":3' in prompts[3]
    assert '"requires_action_sensitivity":false' in prompts[0]
    assert '"requires_action_sensitivity":true' in prompts[1]
    assert program_prompt([entry], candidate_index=0, candidate_count=1) == program_prompt(
        [entry], candidate_index=0, candidate_count=4
    )
