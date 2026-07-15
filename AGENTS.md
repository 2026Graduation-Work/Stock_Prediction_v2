# AGENTS.md

> 행동재무학 기반 심리 지수 반영 주가 예측 플랫폼 (성균관대 졸업작품, 4인 팀).
> 이 파일은 Codex·Claude Code 등 모든 코딩 에이전트의 상시 지침입니다. 상세 기획은 노션 "과제 안내서 v1.2"가 SSOT.

## 프로젝트 한 줄 정의
사용자의 투자 심리를 진단(설문→IPS)해서, ML 예측을 그 사람 성향에 맞게 번역해 보여주는 웹 플랫폼.
연구 질문: "심리 지수를 반영하면 예측이 나아지는가?"

## 저장소 구조
- `backend/profiling/` — 설문·심리 프로파일링 (Python). 담당: 중현(🟡)
- `backend/analysis/chart/` — 단기 예측 LightGBM. 담당: 진세(🟢)
- `backend/analysis/text/` — 뉴스 감성·재무. 담당: 서환(🟢)
- `frontend/` — Next.js 대시보드. 담당: 성우(🔵)
- `schema/` — 블록 간 JSON 계약 (SSOT, freeze됨). 변경 시 전원 합의 필수.
- `.github/` — CI(블록별 3-job), Dependabot, CodeQL

## 개발 환경
- Python: 각 블록 디렉토리 기준. dev 의존성은 `backend/profiling/survey/requirements-dev.txt` (ruff 등)
- Frontend: `frontend/`에서 `pnpm install` → `pnpm dev` / `pnpm build`
- Node: nvm 관리

## 명령어 (커밋·PR 전 필수)
- Python lint: `ruff check .`
- Python test: `pytest`
- Frontend build 검증: `cd frontend && pnpm build`
- 본인 블록 CI가 초록인지 확인 후 리뷰 요청

## PR 규칙
- 항상 새 브랜치 → PR → 리뷰(봇 + 상호) → 머지. main 직접 push 금지.
- 브랜치명: `feat/`, `fix/`, `chore/`, `refactor/` 접두
- 스키마 변경 PR은 제목에 `[schema]` + 전원 멘션
- 커밋: 이동/리네임과 로직 수정은 분리

## 아키텍처 원칙 (위반 금지)
- **화이트박스**: 모든 출력의 근거를 비전공자에게 설명 가능해야 함. "AI가 그렇게 판단" 식 금지.
- **DT 계열 ML만**: 예측기는 LightGBM(GBDT). 딥러닝 보류. 감성 추출만 신경망(FinBERT) 허용.
- **정량/정성 분리**: 점수 산출은 100% 결정론(같은 입력→같은 출력). LLM은 설명 텍스트 생성에만.
- **명시 규칙만 하드 제약**: 사용자가 직접 체크한 회피 항목(`avoided_assets`)만 종목 제거. 성향 점수는 소프트(가중치·임계값).
- **재현성**: 시드 고정 + 공용 평가함수(SSOT). 모델별 자체 평가 코드 금지.
- **HITL**: 자동 매매·손절·익절 실행 금지. 시그널은 선택지로 제시, 최종 판단은 사용자. 근거·출처 항상 표시.
- **표현 제한**: "상승 확률 70%" 단정 금지 → "과거 유사 신호 구간 상위 N%". 미래 주가 점선 곡선 금지(모델은 가격 예측 안 함).

## 데이터 계약 (schema/)
- profiling → analysis/platform: `profiling_output.schema.json` (v1.0 freeze)
- chart → platform: `chart_output.schema.json` (v1.0 freeze)
- text(가치투자) 출력 검증 절차: `backend/analysis/text/VALUE_PIPELINE_VALIDATION.md`
  (위 아키텍처 원칙을 value_pipeline에 적용한 PASS/FAIL 기준·금지 패턴. 출력을
  데이터셋에 넣기 전 필독. 규칙 본문이 아니라 검증 절차이므로 별도 문서로 둔다.)
- 성향별 2모델: `profile_type`(stable/aggressive) ↔ chart `model_type` 매칭
- 회피 태그 체계 통일: profiling `avoided_assets` == chart `risk_flags` enum
- Supabase: 프론트가 DB 직접 조회(별도 API 서버 없음). 스키마 = 사실상 API 계약.

## 하지 말 것
- 다른 팀/조직 레포를 참고할 때 커밋·푸시 금지 (읽기 전용, 분석 후 클론 삭제)
- 팀 산출물에 특정 외부 프로젝트명 명시 금지 → "참고 자료"로 표현
- 유료 기능 활성화 금지 (GitHub Advanced Security 등)
- schema/ 파일을 단독 판단으로 수정 금지 (freeze 상태, 전원 합의 필요)
