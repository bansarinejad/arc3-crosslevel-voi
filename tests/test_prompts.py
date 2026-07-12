from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from arc3_voi.prompts import extract_python, history_payload, parse_action_json


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
    )
    payload = history_payload([entry])
    assert payload[0]["action"] == {"kind": "ACTION6", "row": 2, "col": 3}
    assert len(payload[0]["grid"].splitlines()) == 64
