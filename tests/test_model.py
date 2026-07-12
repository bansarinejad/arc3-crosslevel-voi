from __future__ import annotations

import numpy as np

from arc3_voi.model import ScriptedBackend, _count_generated_tokens, _sequence_token_counts


def test_scripted_backend_is_deterministic() -> None:
    backend = ScriptedBackend(["program_a", "program_b"])
    result = backend.generate_programs([], 3)
    assert result.texts == ("program_a", "program_b", "program_a")
    assert result.tokens_per_second > 0


def test_scripted_direct_policy() -> None:
    backend = ScriptedBackend(action_policy=lambda _history, _valid: {"kind": "ACTION2"})
    action, result = backend.direct_action([], ["ACTION1", "ACTION2"])
    assert action == {"kind": "ACTION2"}
    assert result.output_tokens == 1


def test_count_generated_tokens_stops_at_eos_or_padding() -> None:
    generated = np.array([[10, 11, 2, 0, 0], [20, 21, 22, 0, 0]])

    assert _count_generated_tokens(generated, eos_token_id=2, pad_token_id=0) == 6


def test_sequence_token_counts_flag_only_unterminated_limit() -> None:
    generated = np.array([[10, 11, 2], [20, 21, 22]])

    assert _sequence_token_counts(
        generated, eos_token_id=2, pad_token_id=0, max_new_tokens=3
    ) == ((3, 3), (False, True))
