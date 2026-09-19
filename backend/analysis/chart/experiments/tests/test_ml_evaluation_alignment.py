import pandas as pd
import pytest
from experiments.run_ml_evaluation import _restrict_predictions_to_labeled_rows


def test_ml_evaluation_excludes_only_prediction_rows_without_future_labels() -> None:
    predictions = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
            "Code": ["005930", "005930"],
            "Prob": [0.4, 0.7],
        }
    )
    actual = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2025-01-02"]),
            "Code": ["005930"],
            "Y_Label": [1],
        }
    )

    aligned, excluded = _restrict_predictions_to_labeled_rows(predictions, actual)

    assert excluded == 1
    assert aligned[["Date", "Code", "Prob"]].equals(predictions.iloc[[0]])


def test_ml_evaluation_rejects_missing_prediction_for_labeled_row() -> None:
    predictions = pd.DataFrame(
        {"Date": pd.to_datetime(["2025-01-02"]), "Code": ["005930"], "Prob": [0.4]}
    )
    actual = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2025-01-03"]),
            "Code": ["005930"],
            "Y_Label": [2],
        }
    )

    with pytest.raises(ValueError, match="대응하는 prediction이 없습니다"):
        _restrict_predictions_to_labeled_rows(predictions, actual)
