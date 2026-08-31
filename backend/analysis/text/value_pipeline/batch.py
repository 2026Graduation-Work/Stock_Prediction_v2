"""일별 대량 생성 배치 러너 — LangGraph 파이프라인을 날짜 루프로 호출.

학습 데이터셋(수천~수만 행)을 뽑는 전용 진입점. 한 프로세스 안에서 도는 이유:
- FinBERT 로드 1회 (CLI를 날짜마다 새로 띄우면 실행마다 수 초씩 낭비)
- 빅카인즈 연간 워크북 파싱 캐시 재사용 (20MB 파싱 1회)
- DART/FDR 프로세스 캐시 재사용 (호출이 (종목×사업연도)·(종목)당 1회로 축소)

LLM은 **강제로 끈다** — 대량 생성 중 무료 한도를 태우는 실수를 구조적으로 차단.
숫자는 LLM 유무와 무관하다(test_scores_identical_with_and_without_llm이 보증).

하루 실패가 배치를 죽이지 않는다: 예외는 기록하고 다음 날짜로 넘어가며,
결과 요약(manifest)에 성공/검증실패/에러 건수를 남긴다. 단, 재무 확보 실패
(FinancialsUnavailableError)는 구조적 문제(키 없음 등)이므로 즉시 중단한다.

사용:
    python -m value_pipeline.batch --ticker 005930 --name 삼성전자 \\
        --start 2016-01-01 --end 2025-12-31 --out-dir out/005930
    # 중단 후 재개: --skip-existing (이미 생성된 날짜는 건너뜀)
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


def _iter_days(start: str, end: str):
    day = dt.date.fromisoformat(start)
    stop = dt.date.fromisoformat(end)
    while day <= stop:
        yield day.isoformat()
        day += dt.timedelta(days=1)


def run_batch(
    ticker: str,
    name: str,
    start: str,
    end: str,
    out_dir: Path,
    skip_existing: bool = False,
) -> dict:
    """기간 내 모든 날짜에 대해 일별 파이프라인 실행 → manifest dict 반환."""
    set_llm_enabled(False)  # 대량 생성 경로는 LLM 0콜 (숫자 불변)
    out_dir.mkdir(parents=True, exist_ok=True)

    ok = invalid = skipped = 0
    errors: list[dict] = []
    days = list(_iter_days(start, end))

    for i, d in enumerate(days, start=1):
        out_path = out_dir / f"{ticker}_{d}.json"
        if skip_existing and out_path.exists():
            skipped += 1
            continue
        try:
            result = run_pipeline(ticker, d, name)
        except FinancialsUnavailableError:
            raise  # 구조적 실패(키 없음 등) — 계속 돌아봤자 전부 실패한다
        except Exception as e:  # 그날 하루만 실패로 기록하고 계속
            errors.append({"date": d, "error": repr(e)})
            continue

        out_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if (result.get("validation") or {}).get("ok"):
            ok += 1
        else:
            invalid += 1

        if i % 50 == 0 or i == len(days):
            print(
                f"[진행] {ticker} {i}/{len(days)}일 "
                f"(성공 {ok}, 검증실패 {invalid}, 에러 {len(errors)}, 스킵 {skipped})",
                file=sys.stderr,
            )

    manifest = {
        "ticker": ticker,
        "company_name": name,
        "start": start,
        "end": end,
        "days": len(days),
        "ok": ok,
        "validation_failed": invalid,
        "errors": errors,
        "skipped_existing": skipped,
        "llm": "disabled",
        # 재현 조건 기록: 이 값이 다르면 같은 명령이라도 per/pbr가 다를 수 있다
        "shares_asof_year": SETTINGS.shares_asof_year,
    }
    manifest_path = out_dir / f"_manifest_{ticker}_{start}_{end}.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="일별 가치투자 피처 대량 생성 (LLM 강제 OFF)")
    ap.add_argument("--ticker", required=True, help="종목코드 (예: 005930)")
    ap.add_argument("--name", required=True, help="회사명 (관련성 필터 키워드, 예: 삼성전자)")
    ap.add_argument("--start", required=True, help="시작일 YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="종료일 YYYY-MM-DD")
    ap.add_argument("--out-dir", default="out", help="출력 디렉터리 (기본: out/)")
    ap.add_argument(
        "--skip-existing", action="store_true",
        help="이미 생성된 날짜는 건너뛴다 (중단된 배치 재개용)",
    )
    args = ap.parse_args(argv)

    try:
        manifest = run_batch(
            args.ticker, args.name, args.start, args.end,
            Path(args.out_dir), args.skip_existing,
        )
    except FinancialsUnavailableError as e:
        print(f"[중단] {e}", file=sys.stderr)
        return 2

    print(
        f"[완료] {manifest['days']}일 중 성공 {manifest['ok']}, "
        f"검증실패 {manifest['validation_failed']}, 에러 {len(manifest['errors'])}, "
        f"스킵 {manifest['skipped_existing']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
