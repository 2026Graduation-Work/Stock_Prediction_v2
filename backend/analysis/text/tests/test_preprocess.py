from pathlib import Path

import pandas as pd
import pytest
from analysis.text.preprocess import (
    OUTPUT_COLUMNS,
    BigKindsSchemaError,
    _read_workbook,
    build_news_corpus,
    find_corpus_workbooks,
    find_news_workbook,
    load_daily_news,
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


def test_nested_newsresult_is_shared_and_scoped_by_ticker(tmp_path: Path) -> None:
    """실제 배치 경로의 NewsResult를 corpus와 daily 로더가 함께 찾아야 한다."""
    raw_dir = tmp_path / "raw"
    ticker_dir = raw_dir / "005930"
    ticker_dir.mkdir(parents=True)
    workbook = ticker_dir / "NewsResult_20220101-20221231.xlsx"
    _write_workbook(workbook, [
        {"뉴스 식별자": "n1", "일자": 20220615, "언론사": "매일경제",
         "제목": "중첩 경로 기사", "본문": "본문", "URL": "", "분석제외 여부": ""},
    ])

    assert find_corpus_workbooks(raw_dir, "005930", "삼성전자") == [workbook]
    assert find_news_workbook(
        "삼성전자", "2022-06-15", raw_dir, ticker="005930"
    ) == workbook
    assert [item["news_id"] for item in load_daily_news(
        "삼성전자", "2022-06-15", raw_dir, ticker="005930"
    )] == ["n1"]
    assert find_corpus_workbooks(raw_dir, "000660", "SK하이닉스") == []


def test_newsresult_coverage_uses_actual_dates_not_filename(tmp_path: Path) -> None:
    """상한으로 잘린 파일의 과장된 파일명 기간을 커버리지로 신뢰하지 않는다."""
    ticker_dir = tmp_path / "raw" / "005930"
    ticker_dir.mkdir(parents=True)
    workbook = ticker_dir / "NewsResult_20220101-20221231.xlsx"
    _write_workbook(workbook, [
        {"뉴스 식별자": "n1", "일자": 20220103, "언론사": "매일경제",
         "제목": "실제 첫날", "본문": "본문"},
        {"뉴스 식별자": "n2", "일자": 20220331, "언론사": "한국경제",
         "제목": "상한에서 잘린 마지막 날", "본문": "본문"},
    ])

    assert find_news_workbook(
        "삼성전자", "2022-03-15", tmp_path / "raw", ticker="005930"
    ) == workbook
    assert find_news_workbook(
        "삼성전자", "2022-06-15", tmp_path / "raw", ticker="005930"
    ) is None


def test_daily_loader_merges_and_deduplicates_overlapping_files(tmp_path: Path) -> None:
    ticker_dir = tmp_path / "raw" / "005930"
    ticker_dir.mkdir(parents=True)
    common = {"일자": 20220615, "언론사": "매일경제", "본문": "본문"}
    _write_workbook(ticker_dir / "NewsResult_part1.xlsx", [
        {**common, "뉴스 식별자": "n1", "제목": "중복 기사"},
    ])
    _write_workbook(ticker_dir / "NewsResult_part2.xlsx", [
        {**common, "뉴스 식별자": "n1", "제목": "중복 기사"},
        {**common, "뉴스 식별자": "n2", "제목": "추가 기사"},
    ])

    items = load_daily_news(
        "삼성전자", "2022-06-15", tmp_path / "raw", limit=None, ticker="005930"
    )
    assert [item["news_id"] for item in items] == ["n1", "n2"]


def test_daily_loader_reuses_pre_resolved_workbooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ticker_dir = tmp_path / "raw" / "005930"
    ticker_dir.mkdir(parents=True)
    workbook = ticker_dir / "NewsResult_part1.xlsx"
    _write_workbook(workbook, [
        {"뉴스 식별자": "n1", "일자": 20220615, "언론사": "매일경제",
         "제목": "한 번 찾은 파일", "본문": "본문"},
    ])
    monkeypatch.setattr(
        "analysis.text.preprocess.find_news_workbooks",
        lambda *args, **kwargs: pytest.fail("워크북 디렉터리를 다시 탐색했습니다."),
    )

    items = load_daily_news(
        "삼성전자",
        "2022-06-15",
        tmp_path / "raw",
        ticker="005930",
        workbooks=[workbook],
    )

    assert [item["news_id"] for item in items] == ["n1"]
