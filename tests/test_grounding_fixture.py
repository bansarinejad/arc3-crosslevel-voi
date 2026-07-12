from __future__ import annotations

import json
from pathlib import Path

from arc3_voi.grounding_repair import GroundedSource
from arc3_voi.replay import history_from_records
from scripts.prompt_grounding_smoke import (
    _fixture_history_records,
    _history_sha256,
    _program_payloads,
)


def test_frozen_grounding_fixture_decodes_to_declared_history() -> None:
    fixture = json.loads(
        Path("fixtures/grounding/bp35_seed11_initial_history.json").read_text(encoding="utf-8")
    )

    records = _fixture_history_records(fixture)
    history = history_from_records(records)

    assert _history_sha256(records) == fixture["history_canonical_sha256"]
    assert history.latest_grid.shape == (64, 64)
    assert sorted(int(value) for value in set(history.latest_grid.flat)) == [
        0,
        3,
        5,
        9,
        10,
        11,
        14,
    ]


def test_schema_v5_program_payload_preserves_global_and_batch_local_indices() -> None:
    sources = tuple(
        GroundedSource(batch, candidate, f"source-{batch}-{candidate}", None, "error")
        for batch in range(2)
        for candidate in range(4)
    )

    payloads = _program_payloads(sources)

    assert [row["candidate_index"] for row in payloads] == list(range(8))
    assert [row["batch_index"] for row in payloads] == [0] * 4 + [1] * 4
    assert [row["batch_candidate_index"] for row in payloads] == [0, 1, 2, 3] * 2
