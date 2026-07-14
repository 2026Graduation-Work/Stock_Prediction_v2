"""CLI 실행기 — 가치투자 피처 JSON 생성.

예시:
    python -m value_pipeline.run                       # 삼성전자(005930), 오늘 날짜
    python -m value_pipeline.run --ticker 000660        # SK하이닉스
    python -m value_pipeline.run --ticker 005930 --date 2026-05-17 --out out.json

뉴스는 data/의 로컬 엑셀 파일을 우선 사용한다.
API 키가 없으면 동봉 샘플 + 규칙 기반으로 끝까지 동작하고,
.env에 GEMINI_API_KEY / DART_API_KEY 를 넣으면 자동으로 실데이터로 전환된다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from .config import SETTINGS
from .graph import run_pipeline


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="가치투자 데이터 → 구조화 JSON 피처 전처리")
    ap.add_argument("--ticker", default="005930", help="종목코드 (기본: 005930 삼성전자)")
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="기준일 YYYY-MM-DD")
    ap.add_argument("--name", default="", help="회사명 (뉴스 검색 정확도 향상용)")
    ap.add_argument("--out", default="", help="출력 JSON 경로 (기본: <ticker>_<date>.json)")
    args = ap.parse_args(argv)

    print(
        f"[설정] Gemini={'ON' if SETTINGS.has_gemini else 'OFF(규칙기반)'}, "
        f"DART={'ON' if SETTINGS.has_dart else 'OFF(샘플)'}, "
        f"News=Excel(data/) 우선"
        f"{'→Naver API' if SETTINGS.has_naver else '→크롤/샘플'}, "
        f"FinBERT={'시도' if SETTINGS.use_finbert else 'OFF'}",
        file=sys.stderr,
    )

    result = run_pipeline(args.ticker, args.date, args.name)

    out_path = Path(args.out) if args.out else Path(f"{args.ticker}_{args.date}.json")
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n[저장] {out_path.resolve()}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
