from pathlib import Path

import pandas as pd
import pytest
from analysis.text.preprocess import (
    OUTPUT_COLUMNS,
    BigKindsSchemaError,
    _read_workbook,
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


def test_parses_date_strings_with_time_as_datetime64(tmp_path: Path) -> None:
    workbook = tmp_path / "NewsResult_dates.xlsx"
    _write_workbook(
        workbook,
        [
            {
                "일자": "2025-01-01 00:00:00",
                "제목": "초 단위 시간",
                "본문": "본문",
                "언론사": "테스트일보",
            },
            {
                "일자": "2025.01.02 09:00",
                "제목": "분 단위 시간",
                "본문": "본문",
                "언론사": "테스트일보",
            },
        ],
    )

    normalized = _read_workbook(workbook)

    assert pd.api.types.is_datetime64_any_dtype(normalized["date"])
    assert normalized["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2025-01-01",
        "2025-01-02",
    ]


def test_ignores_excel_temporary_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    workbook = raw_dir / "NewsResult_valid.xlsx"
    temporary_workbook = raw_dir / "~$NewsResult_open.xlsx"
    _write_workbook(
        workbook,
        [
            {
                "뉴스 식별자": "news-1",
                "일자": 20250101,
                "제목": "정상 기사",
                "본문": "본문",
                "언론사": "테스트일보",
            }
        ],
    )
    temporary_workbook.write_bytes(b"not an Excel workbook")
    monkeypatch.setattr(
        Path,
        "glob",
        lambda self, pattern: iter([workbook, temporary_workbook]),
    )

    report = build_news_corpus("005930", tmp_path / "output.csv", raw_dir)

    assert report.input_files == 1
    assert report.raw_rows == 1


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


def test_reads_only_the_requested_ticker_directory(tmp_path: Path) -> None:
    """종목별 하위 디렉터리(raw/<종목코드>/)가 있으면 그 종목만 읽어 혼입을 막는다."""
    raw_dir = tmp_path / "raw"
    samsung_dir = raw_dir / "005930"
    kakao_dir = raw_dir / "035720"
    samsung_dir.mkdir(parents=True)
    kakao_dir.mkdir()
    base_row = {
        "일자": 20250101,
        "제목": "종목 기사",
        "본문": "본문",
        "언론사": "테스트일보",
    }
    _write_workbook(
        samsung_dir / "NewsResult_20250101-20250131.xlsx",
        [{**base_row, "뉴스 식별자": "samsung-news"}],
    )
    _write_workbook(
        kakao_dir / "NewsResult_20250101-20250131.xlsx",
        [{**base_row, "뉴스 식별자": "kakao-news"}],
    )

    output_path = tmp_path / "news_corpus.csv"
    report = build_news_corpus("005930", output_path, raw_dir)
    result = pd.read_csv(output_path, dtype={"ticker": str})

    assert report.input_files == 1
    assert result["news_id"].tolist() == ["samsung-news"]
    assert result["ticker"].tolist() == ["005930"]


def test_raises_when_ticker_directory_missing_but_others_exist(tmp_path: Path) -> None:
    """다른 종목 폴더는 있는데 요청 종목 폴더가 없으면, 엉뚱한 데이터로 코퍼스를
    만들지 않도록 즉시 멈춘다(코퍼스 빌더는 strict)."""
    raw_dir = tmp_path / "raw"
    (raw_dir / "035720").mkdir(parents=True)
    row: dict[str, object] = {
        "뉴스 식별자": "kakao-news",
        "일자": 20250101,
        "제목": "기사",
        "본문": "본문",
        "언론사": "테스트일보",
    }
    _write_workbook(
        raw_dir / "035720" / "NewsResult_20250101-20250131.xlsx", [row]
    )

    with pytest.raises(FileNotFoundError) as error:
        build_news_corpus("005930", tmp_path / "output.csv", raw_dir)

    message = str(error.value)
    assert "005930" in message
    assert "035720" in message  # 현재 존재하는 종목 디렉터리를 안내
