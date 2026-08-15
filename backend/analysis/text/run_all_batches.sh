#!/usr/bin/env bash
# value_pipeline 다종목 일별 배치 러너 — 전 종목 학습 데이터셋 생성.
#
# 사용:
#   bash backend/analysis/text/run_all_batches.sh        # 저장소 어디서든 실행 가능
#
# - 종목별로 python -m value_pipeline.batch 를 순차 실행 (LLM 강제 OFF, 캐시 활용)
# - --skip-existing 이라 중단돼도 같은 명령으로 재개되고, 이미 뽑은 구간은 건너뜀
# - 한 종목이 실패해도 다음 종목은 계속 진행하고, 끝에 요약을 출력
#
# 시작일 근거 (DART 사업보고서 공시 시점 — 이전 날짜는 재무가 없어 즉시 중단됨):
# - 상장 대형사(삼성전자·네이버·현대차): DART 재무가 FY2015부터 → 2016-04-01 이후 가능.
#   팀 결정으로 2017-01-01 사용.
# - 에코프로비엠: 2019-03 상장, 첫 사업보고서가 FY2018(2019-04 공시) → 2019-04-01부터.
#   FY2018~19는 연결재무제표가 없어 별도(OFS) 폴백으로 처리된다 (collectors.py).

set -u

REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
TEXT_DIR="$REPO/backend/analysis/text"
cd "$TEXT_DIR" || { echo "[중단] text 디렉터리로 이동 실패"; exit 1; }

# 휴지통 등 저장소 밖에서 도는 사고 방지 (pwd가 git 저장소 안인지 확인)
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || { echo "[중단] git 저장소 밖입니다: $(pwd) — 경로를 확인하세요"; exit 1; }

source "$REPO/.venv/bin/activate" || { echo "[중단] .venv 활성화 실패"; exit 1; }

END="2025-12-31"
# 형식: 종목코드|회사명|시작일
TARGETS=(
  "005930|삼성전자|2017-01-01"
  "035420|네이버|2017-01-01"
  "005380|현대차|2017-01-01"
  "247540|에코프로비엠|2019-04-01"
)

SUMMARY=""
for entry in "${TARGETS[@]}"; do
  IFS="|" read -r TICKER NAME START <<< "$entry"
  echo ""
  echo "===== $NAME($TICKER) $START ~ $END ====="
  SECONDS=0
  python -m value_pipeline.batch \
    --ticker "$TICKER" --name "$NAME" \
    --start "$START" --end "$END" \
    --out-dir "out/$TICKER" --skip-existing
  CODE=$?
  MIN=$((SECONDS / 60))
  SEC=$((SECONDS % 60))
  SUMMARY+="$NAME($TICKER): exit=$CODE, ${MIN}분 ${SEC}초"$'\n'
  [ $CODE -ne 0 ] && echo "[경고] $NAME 배치가 exit=$CODE 로 끝남 — manifest/로그 확인 필요"
done

echo ""
echo "===== 전체 요약 ====="
printf '%s' "$SUMMARY"
echo ""
echo "다음 단계 (종목별 학습용 CSV):"
for entry in "${TARGETS[@]}"; do
  IFS="|" read -r TICKER NAME START <<< "$entry"
  echo "  python -m value_pipeline.features out/$TICKER/*.json --out features_${TICKER}_daily.csv"
done
