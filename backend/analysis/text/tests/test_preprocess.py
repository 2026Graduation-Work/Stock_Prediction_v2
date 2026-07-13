from pathlib import Path

import pandas as pd
import pytest
from analysis.text.preprocess import (
    OUTPUT_COLUMNS,
    BigKindsSchemaError,
    build_news_corpus,
    print_report,
)


def _write_workbook(path: Path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_excel(path, index=False, engine="openpyxl")


def test_merges_overlapping_files_and_deduplicates_by_news_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    common = {
        "뉴스 식별자": "news-2",
        "일자": 20250103,
        "제목": "겹치는 기사",
        "본문": "같은 본문",
        "언론사": "테스트일보",
    }
    _write_workbook(
        raw_dir / "NewsResult_20250101-20250103.xlsx",
        [
            {
                "뉴스 식별자": "news-1",
                "일자": 20250101,
                "제목": "첫 기사",
                "본문": "첫 본문",
                "언론사": "테스트일보",
            },
            common,
        ],
    )
    _write_workbook(
        raw_dir / "NewsResult_20250103-20250105.xlsx",
        [
            common,
            {
                "뉴스 식별자": "news-3",
                "일자": 20250105,
                "제목": "마지막 기사",
                "본문": "마지막 본문",
                "언론사": "경제일보",
            },
        ],
    )

    output_path = tmp_path / "news_corpus.csv"
    report = build_news_corpus("005930", output_path, raw_dir)
    print_report(report)

    result = pd.read_csv(output_path, dtype={"ticker": str})
    assert list(result.columns) == OUTPUT_COLUMNS
    assert result["news_id"].tolist() == ["news-1", "news-2", "news-3"]
    assert result["ticker"].tolist() == ["005930"] * 3
    assert report.input_files == 2
    assert report.raw_rows == 4
    assert report.deduplicated_rows == 3
    assert report.missing_dates == ("2025-01-02", "2025-01-04")

    stdout = capsys.readouterr().out
    assert "입력 파일 수: 2" in stdout
    assert "원본 총 건수: 4" in stdout
    assert "dedup 후 건수: 3" in stdout
    assert "실제 수록 기간: 2025-01-01 ~ 2025-01-05" in stdout
    assert "일자 구멍 개수: 2" in stdout


def test_uses_fallback_key_and_keywords_when_optional_columns_are_missing(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    duplicate = {
        "일자": "2025-02-01",
        "제목": "식별자 없는 기사",
        "키워드": "반도체, 실적",
        "언론사": "경제일보",
    }
    _write_workbook(raw_dir / "NewsResult_a.xlsx", [duplicate])
    nested_dir = raw_dir / "nested"
    nested_dir.mkdir()
    _write_workbook(nested_dir / "NewsResult_b.xlsx", [duplicate])

    output_path = tmp_path / "news_corpus.csv"
    report = build_news_corpus("005930", output_path, raw_dir)
    result = pd.read_csv(output_path)

    assert report.input_files == 2
    assert report.deduplicated_rows == 1
    assert result.loc[0, "body"] == "반도체, 실적"
    assert result.loc[0, "news_id"].startswith("generated:")


def test_fails_with_clear_error_when_required_column_is_missing(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _write_workbook(
        raw_dir / "NewsResult_missing_press.xlsx",
        [{"일자": 20250101, "제목": "언론사 없음", "본문": "본문"}],
    )

    with pytest.raises(BigKindsSchemaError) as error:
        build_news_corpus("005930", tmp_path / "output.csv", raw_dir)

    message = str(error.value)
    assert "NewsResult_missing_press.xlsx" in message
    assert "press" in message
    assert "언론사" in message
