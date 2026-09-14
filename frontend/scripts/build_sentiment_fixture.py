"""삼성전자 감성 픽스처 생성: news_corpus.csv 실데이터 → frontend/lib/providers/sentiment-fixture.ts

backend value_pipeline news_agent와 같은 규칙으로 일별 감성을 낸다.
    관련성 필터(relevant_indices) → 하루 최대 max_daily_articles건
    → score_texts(KR-FinBERT) → aggregate 평균
기사 텍스트는 preprocess.load_daily_news와 같이 제목 + 본문 앞 1000자(summary)다.
대표 기사는 news_agent 규칙 폴백과 같이 최근일 감성 절댓값 상위 3건이다.

N07 "뉴스 감성 급변" 임계는 전체 기간 일별 감성 변화량 |Δ|의 상위 10% 분위수(p90)다.

실행
    전수(기본, torch·transformers 필요):
        python frontend/scripts/build_sentiment_fixture.py
    빠른 플레이스홀더(사전 폴백, 몇 초):
        python frontend/scripts/build_sentiment_fixture.py --limit 300 --scorer dictionary
기본 옵션에서 KR-FinBERT를 못 불러오면 중단한다
(VALUE_PIPELINE_VALIDATION.md: 감성 백엔드 혼용 금지). 사전 결과는 PLACEHOLDER로 표시한다.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXT_BLOCK = ROOT / "backend" / "analysis" / "text"
sys.path.insert(0, str(TEXT_BLOCK))

from value_pipeline.agents import _text_of, relevant_indices  # noqa: E402
from value_pipeline.config import SETTINGS  # noqa: E402
from value_pipeline.sentiment import _lexicon_score, aggregate, score_texts  # noqa: E402

CORPUS = TEXT_BLOCK / "data" / "processed" / "news_corpus.csv"
OUT = ROOT / "frontend" / "lib" / "providers" / "sentiment-fixture.ts"
TICKER = "005930"
COMPANY = "삼성전자"
BODY_CHARS = 1000  # preprocess.load_daily_news 기본값
WINDOW_DAYS = 20
HEADLINES = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--scorer",
        choices=("finbert", "dictionary"),
        default="finbert",
        help="finbert = KR-FinBERT(기본), dictionary = value_pipeline 사전 폴백",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="전체 채점 기사 수 상한. 날짜마다 고르게 나눈다(날짜당 최소 1건)",
    )
    return parser.parse_args()


def load_corpus() -> dict[str, list[dict]]:
    by_day: dict[str, list[dict]] = defaultdict(list)
    with CORPUS.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            title = row["title"].strip()
            if row["ticker"] != TICKER or not title:
                continue
            by_day[row["date"][:10]].append(
                {
                    "news_id": row["news_id"],
                    "title": title,
                    "summary": row["body"].strip()[:BODY_CHARS],
                    "press": row["press"].strip(),
                }
            )
    # load_daily_news와 같이 하루 안에서는 news_id 순
    return {
        date: sorted(items, key=lambda item: item["news_id"])
        for date, items in sorted(by_day.items())
    }


def score(texts: list[str], scorer: str) -> list[float]:
    if scorer == "dictionary":
        return [_lexicon_score(text) for text in texts]
    scores, backend = score_texts(texts)
    if backend != "kr-finbert":
        raise SystemExit(f"감성 백엔드가 {backend}입니다. KR-FinBERT 환경에서 실행하세요.")
    return scores


def main() -> None:
    args = parse_args()
    corpus = load_corpus()
    per_day = SETTINGS.max_daily_articles
    if args.limit is not None:
        per_day = max(1, min(per_day, args.limit // len(corpus)))

    days: list[dict] = []
    for date, items in corpus.items():
        relevant = [items[index] for index in relevant_indices(items, COMPANY)][:per_day]
        if not relevant:
            # 기사 0건인 날의 0.0은 관측이 아니다. 변화량 분포에서도 뺀다.
            continue
        scores = score([_text_of(item) for item in relevant], args.scorer)
        mean, _std = aggregate(scores)
        ranked = sorted(zip(relevant, scores), key=lambda pair: abs(pair[1]), reverse=True)
        days.append(
            {
                "date": date,
                "score": mean,
                "articleCount": len(relevant),
                "headlines": [
                    {"date": date, "title": item["title"], "press": item["press"]}
                    for item, _score in ranked[:HEADLINES]
                ],
            }
        )
        print(f"{date} n={len(relevant)} score={mean:+.4f}", file=sys.stderr, flush=True)

    changes = [abs(current["score"] - previous["score"]) for previous, current in zip(days, days[1:])]
    p90 = round(statistics.quantiles(changes, n=10, method="inclusive")[-1], 4)
    window = days[-WINDOW_DAYS:]
    series = {
        "days": [
            {key: day[key] for key in ("date", "score", "articleCount")} for day in window
        ],
        "headlines": window[-1]["headlines"],
    }
    scored = sum(day["articleCount"] for day in days)

    header: list[str] = []
    if args.scorer != "finbert" or args.limit is not None:
        scorer_label = "사전 기반" if args.scorer == "dictionary" else "FinBERT"
        sample = f"{args.limit}건 표본" if args.limit is not None else "전수"
        header.append(f"// PLACEHOLDER — {scorer_label} {sample}. FinBERT 전수 결과로 교체 대기 중.")
    backend = (
        f"kr-finbert ({SETTINGS.finbert_model})"
        if args.scorer == "finbert"
        else "dictionary (value_pipeline.sentiment 사전 폴백 39단어)"
    )
    limit_flag = f" --limit {args.limit}" if args.limit is not None else ""
    OUT.write_text(
        "\n".join(
            [
                *header,
                "// FIXTURE — 실데이터 아님.",
                "// 단, 삼성전자(005930) 감성 점수와 기사 제목은 실제 기사에서 집계했다. 자동 생성 파일이므로 직접 고치지 않는다.",
                f"// 생성: python frontend/scripts/build_sentiment_fixture.py --scorer {args.scorer}{limit_flag}",
                "//       (backend value_pipeline news_agent와 같은 규칙)",
                f"// 원천: backend/analysis/text/data/processed/news_corpus.csv, {days[0]['date']} ~ {days[-1]['date']} 중 관련 기사가 있는 {len(days)}일, 채점 {scored}건",
                f"// 감성 백엔드: {backend}, 기사 텍스트 = 제목 + 본문 앞 {BODY_CHARS}자",
                f"// N07 임계: 일별 감성 변화량 |Δ| {len(changes)}개의 상위 10% 분위수(p90, inclusive 보간) = {p90}",
                "// 코퍼스 기간이 화면의 예측 기준일(2025-10-02)보다 뒤다. 기간 정렬은 실데이터 연동 때 맞춘다.",
                "",
                'import type { SentimentSeries } from "./index";',
                "",
                f"export const SENTIMENT_SHIFT_P90 = {p90};",
                "",
                "export const SAMSUNG_SENTIMENT: SentimentSeries = "
                + json.dumps(series, ensure_ascii=False, indent=2)
                + ";",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"wrote {OUT} (days={len(days)}, scored={scored}, p90={p90})", file=sys.stderr)


if __name__ == "__main__":
    main()
