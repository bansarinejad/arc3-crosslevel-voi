from __future__ import annotations

import json
from pathlib import Path

from arc3_voi.splitting import (
    GameMetadata,
    load_metadata,
    metadata_hash,
    stratified_split,
)


def _games() -> list[GameMetadata]:
    return [
        GameMetadata(
            game_id=f"g{index:02}",
            version=f"v{index}",
            tags=("keyboard_click" if index % 3 == 0 else "keyboard",),
            win_levels=2 + index % 8,
            baseline_actions=(5 + index, 8 + index),
        )
        for index in range(25)
    ]


def test_split_is_deterministic_and_has_required_sizes() -> None:
    first = stratified_split(_games())
    second = stratified_split(list(reversed(_games())))
    assert len(first.development) == 15
    assert len(first.confirmation) == 10
    assert set(first.development).isdisjoint(first.confirmation)
    assert first.algorithm == "iterative-multilabel-v1"
    assert first.game_versions["g00"] == "v0"
    # Snapshot order is not semantically relevant.
    assert first == second


def test_metadata_hash_ignores_input_order() -> None:
    assert metadata_hash(_games()) == metadata_hash(list(reversed(_games())))


def test_frozen_public_split_matches_iterative_algorithm() -> None:
    root = Path(__file__).parents[1]
    games = load_metadata(root / "artifacts/public_games.snapshot.json")
    expected = json.loads((root / "artifacts/public_split.json").read_text())
    actual = stratified_split(games, development_size=15, seed=20_260_712)
    assert list(actual.development) == expected["development"]
    assert list(actual.confirmation) == expected["confirmation"]
    assert actual.game_versions == expected["game_versions"]
