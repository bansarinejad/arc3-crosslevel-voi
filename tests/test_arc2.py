from __future__ import annotations

import numpy as np

from arc3_voi.arc2 import Arc2Task, committee_output, exact_mcnemar, training_loss


class Identity:
    ast_nodes = 1

    def apply(self, grid: np.ndarray) -> np.ndarray:
        return grid.copy()


class Zero:
    ast_nodes = 1

    def apply(self, grid: np.ndarray) -> np.ndarray:
        return np.zeros_like(grid)


def test_training_loss_and_weighted_committee() -> None:
    grid = np.asarray([[1, 2], [3, 4]], dtype=np.int8)
    task = Arc2Task("x", ((grid, grid),), ((grid, grid),))
    assert training_loss(Identity(), task) == 0
    output, agreement = committee_output([Identity(), Zero()], [0.8, 0.2], grid)
    assert np.array_equal(output, grid)
    assert agreement == 0.8


def test_exact_mcnemar_no_disagreement() -> None:
    assert exact_mcnemar([True, False], [True, False]) == 1.0

