# ruff: noqa: I001

import pandas as pd

from experiments.experiment_utils import build_fold_alignment


SPLITS = [{"fold_id": 0, "name": "fold-0", "test_start": "2024-01-01", "test_end": "2024-01-31"}]


def test_fold_alignment_rejects_missing_actual_label_key() -> None:
    predictions = pd.DataFrame(
        {"Date": pd.to_datetime(["2024-01-02", "2024-01-03"]), "Code": ["000001", "000002"]}
    )
    actuals = predictions.iloc[[0]].assign(Y_Label=1)

    _, status = build_fold_alignment(predictions, SPLITS, eval_df=actuals)
    assert not status["is_exact_row_match"]


def test_fold_alignment_rejects_duplicate_actual_keys() -> None:
    predictions = pd.DataFrame(
        {"Date": pd.to_datetime(["2024-01-02", "2024-01-03"]), "Code": ["000001", "000002"]}
    )
    actuals = pd.concat([predictions, predictions.iloc[[0]]], ignore_index=True).assign(Y_Label=1)

    _, status = build_fold_alignment(predictions, SPLITS, eval_df=actuals)
    assert not status["is_exact_row_match"]
