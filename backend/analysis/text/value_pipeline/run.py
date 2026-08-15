"""CLI 실행기 — 가치투자 피처 JSON 생성.

예시:
    python -m value_pipeline.run                       # 삼성전자(005930), 오늘 날짜
    python -m value_pipeline.run --ticker 000660        # SK하이닉스
    python -m value_pipeline.run --ticker 005930 --date 2026-05-17 --out out.json
    python -m value_pipeline.run --ticker 005930 --name 삼성전자 --period 2022-01
                                                        # 기간(월) 요약 1건

뉴스는 data/의 로컬 엑셀 파일(빅카인즈)을 우선 사용한다.
.env에 DART_API_KEY가 필요하다 — 재무 없이는 시그널을 만들지 않는다(exit 2).
GEMINI_API_KEY가 있으면 뉴스 관련성 필터·근거 생성에 쓰이고, 없으면 규칙 기반으로
동작한다. LLM 출력은 content-hash로 캐시되어 재실행 시 결정론이 유지된다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from .collectors import FinancialsUnavailableError
from .config import SETTINGS
from .graph import run_pipeline
from .llm import set_llm_enabled
from .period import parse_period, run_period_pipeline


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="가치투자 데이터 → 구조화 JSON 피처 전처리")
    ap.add_argument("--ticker", default="005930", help="종목코드 (기본: 005930 삼성전자)")
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="기준일 YYYY-MM-DD")
    ap.add_argument(
        "--period", default="",
        help="기간 모드: YYYY 또는 YYYY-MM. 지정 시 --date 무시, 재무는 기간 종료일 기준",
    )
    ap.add_argument("--name", default="", help="회사명 (뉴스 검색 정확도 향상용)")
    ap.add_argument(
        "--out", default="",
        help="출력 JSON 경로 (기본: <ticker>_<date>.json, 기간 모드는 <ticker>_<period>.json)",
    )
    ap.add_argument(
        "--no-llm", action="store_true",
        help=".env에 GEMINI_API_KEY가 있어도 LLM 호출을 끈다 — 모든 숫자는 동일하고 "
             "이벤트·근거 텍스트만 규칙/캐시 폴백. 대량 생성 시 무료 한도 보호용",
    )
    args = ap.parse_args(argv)

    if args.no_llm:
        set_llm_enabled(False)

    if args.period:
        try:
            parse_period(args.period)  # 수집 시작 전에 형식 오류를 잡는다
        except ValueError as e:
            ap.error(str(e))

    gemini_status = (
        "OFF(--no-llm)" if args.no_llm
        else ("ON" if SETTINGS.has_gemini else "OFF(규칙기반)")
    )
    print(
        f"[설정] Gemini={gemini_status}, "
        f"DART={'ON' if SETTINGS.has_dart else 'OFF'}, "
        f"News=Excel(data/) 우선"
        f"{'→Naver API' if SETTINGS.has_naver else '→크롤'}, "
        f"FinBERT={'시도' if SETTINGS.use_finbert else 'OFF'}, "
        f"LLM재생전용={'ON' if SETTINGS.llm_replay_only else 'OFF'}",
        file=sys.stderr,
    )

    try:
        if args.period:
            result = run_period_pipeline(args.ticker, args.period, args.name)
        else:
            result = run_pipeline(args.ticker, args.date, args.name)
    except FinancialsUnavailableError as e:
        print(f"[중단] {e}", file=sys.stderr)
        return 2

    default_out = f"{args.ticker}_{args.period or args.date}.json"
    out_path = Path(args.out) if args.out else Path(default_out)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))

    validation = result.get("validation") or {}
    for w in validation.get("warnings", []):
        print(f"[경고] {w}", file=sys.stderr)
    for err in validation.get("errors", []):
        print(f"[검증실패] {err}", file=sys.stderr)
    print(f"\n[저장] {out_path.resolve()}", file=sys.stderr)
    if not validation.get("ok", True):
        print("[결과] 검증 실패 — 이 행을 데이터셋에 넣지 마세요.", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
