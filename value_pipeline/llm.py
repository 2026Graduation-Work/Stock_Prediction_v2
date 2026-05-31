"""Gemini 무료 티어 LLM 래퍼 (선택적).

GEMINI_API_KEY 가 있으면 langchain-google-genai로 구조화 출력을 받고,
없으면 None을 반환해 각 에이전트가 규칙 기반 폴백으로 동작하게 한다.

LLM이 담당하는 부분(보조): 핵심 이벤트 추출, 자연어 근거, 시그널 보강.
수치 피처(감성·재무점수)는 결정론 모듈이 책임진다.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@lru_cache(maxsize=1)
def get_llm():
    """Gemini chat 모델 또는 None."""
    from .config import SETTINGS

    if not SETTINGS.has_gemini:
        return None
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=SETTINGS.gemini_model,
            google_api_key=SETTINGS.gemini_api_key,
            temperature=0.2,
        )
    except Exception:
        return None


def structured(prompt: str, schema: type[T]) -> Optional[T]:
    """프롬프트 → 구조화(schema) 결과. LLM 미사용/실패 시 None."""
    llm = get_llm()
    if llm is None:
        return None
    try:
        return llm.with_structured_output(schema).invoke(prompt)
    except Exception:
        return None
