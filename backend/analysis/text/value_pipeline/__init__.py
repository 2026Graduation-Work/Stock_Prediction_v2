"""가치투자 데이터 전처리 파이프라인 (한국 주식).

뉴스 / 재무제표를 수집해 멀티 에이전트(LangGraph)로 분석·검증하고,
다운스트림 주가예측 모델이 바로 쓸 수 있는 구조화 JSON 피처를 생성한다.

    ingest → {news_agent ∥ financial_agent} → validation_agent → synthesis_agent

점수는 100% 결정론으로 산출한다 — 뉴스 관련성 판정까지 포함해서다. 어떤 기사를
채점할지 LLM이 정하면 그건 곧 점수를 LLM이 정하는 것이기 때문이다.
LLM(Gemini)은 핵심 이벤트 추출·근거 문장 생성만 담당하며 어떤 숫자에도 영향을 주지
않는다(GEMINI_API_KEY 유무로 숫자가 바뀌면 버그다).
DART_API_KEY는 필수다 — 재무 없이는 시그널을 만들지 않는다.

검증 기준: VALUE_PIPELINE_VALIDATION.md
"""

from .schema import ValueSignal

__all__ = ["ValueSignal"]
