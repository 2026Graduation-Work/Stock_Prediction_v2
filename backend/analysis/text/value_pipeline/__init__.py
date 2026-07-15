"""가치투자 데이터 전처리 파이프라인 (한국 주식).

뉴스 / 재무제표를 수집해 멀티 에이전트(LangGraph)로 분석·검증하고,
다운스트림 주가예측 모델이 바로 쓸 수 있는 구조화 JSON 피처를 생성한다.

    ingest → {news_agent ∥ financial_agent} → validation_agent → synthesis_agent

점수는 100% 결정론으로 산출한다. LLM(Gemini)은 뉴스 관련성 라벨링·핵심 이벤트
추출·근거 문장 생성만 담당하며, 출력은 content-hash 캐시로 동결되어 재실행 시
결정론이 유지된다. GEMINI_API_KEY가 없으면 규칙 기반으로 동작한다.
DART_API_KEY는 필수다 — 재무 없이는 시그널을 만들지 않는다.

검증 기준: VALUE_PIPELINE_VALIDATION.md
"""

from .schema import ValueSignal

__all__ = ["ValueSignal"]
