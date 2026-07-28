"""Gemini 무료 티어 LLM 래퍼 (선택적) + 결정론 보장 캐시.

GEMINI_API_KEY 가 있으면 langchain-google-genai로 구조화 출력을 받고,
없으면 None을 반환해 각 에이전트가 규칙 기반 폴백으로 동작하게 한다.

LLM이 담당하는 부분: 뉴스 관련성·이벤트 라벨링(추출), 자연어 근거 생성.
점수(감성·재무점수·영향력·시그널·신뢰도)는 결정론 모듈이 책임진다.

## 왜 캐시가 필수인가

LLM은 temperature=0으로도 결정론이 아니다 — 서버가 함께 배치하는 요청 수에 따라
커널 결과가 달라지기 때문(batch invariance)이며, 이는 우리 통제 밖이다.
그래서 결정론을 '모델'이 아니라 '인터페이스 경계'에서 확보한다: LLM은 한 번만 돌고
출력은 content-hash 키로 동결되며, 재실행은 파일을 읽는다.

캐시 키에 프롬프트·모델·스키마·파라미터를 전부 넣어야 한다. 프롬프트가 빠지면
프롬프트를 고쳐도 옛 답이 나오는 조용한 staleness가 생긴다(가장 흔한 버그).

부수 효과: 독점 모델은 은퇴하고, 은퇴한 모델의 출력은 복구 불가능하다. 캐시가
완전하면 모델이 사라져도 결과를 재현할 수 있다(robust reproducibility).
"""
from __future__ import annotations

import hashlib
import json
import warnings
from functools import lru_cache
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .config import SETTINGS

T = TypeVar("T", bound=BaseModel)

CACHE_DIR = Path(__file__).parent / "llm_cache"

# 프롬프트 템플릿을 바꾸면 이 값을 올린다 → 캐시 키가 바뀌어 옛 답이 재사용되지 않는다.
PROMPT_VERSION = "1"


class LLMCacheMissError(RuntimeError):
    """재생(replay) 모드인데 캐시에 없음 → LLM 호출 대신 실패."""


@lru_cache(maxsize=1)
def get_llm():
    """Gemini chat 모델 또는 None."""
    if not SETTINGS.has_gemini:
        return None
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=SETTINGS.gemini_model,
            google_api_key=SETTINGS.gemini_api_key,
            temperature=0.0,
        )
    except Exception:
        return None


def _cache_key(prompt: str, schema: type[BaseModel]) -> str:
    """프롬프트·스키마·모델·파라미터 전부를 키에 넣는다 (staleness 방지)."""
    payload = "\x1f".join(
        [
            prompt,
            schema.__name__,
            json.dumps(schema.model_json_schema(), sort_keys=True, ensure_ascii=False),
            SETTINGS.gemini_model,
            "temp=0.0",
            f"promptver={PROMPT_VERSION}",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def structured(prompt: str, schema: type[T]) -> T | None:
    """프롬프트 → 구조화(schema) 결과. LLM 미사용/실패 시 None.

    캐시 히트면 LLM을 호출하지 않는다 → 같은 입력 재실행 시 완전 결정론.
    LLM_REPLAY_ONLY=1 이면 캐시 미스가 LLMCacheMissError (백테스트 재생용).
    """
    key = _cache_key(prompt, schema)
    path = _cache_path(key)

    if path.exists():
        try:
            return schema.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as e:
            warnings.warn(f"LLM 캐시 파손({key[:12]}), 재생성합니다: {e}", stacklevel=2)

    if SETTINGS.llm_replay_only:
        raise LLMCacheMissError(
            f"재생 모드인데 LLM 캐시에 없습니다 (key={key[:12]}). "
            f"LLM_REPLAY_ONLY=0으로 캐시를 먼저 생성하세요. "
            f"재생 중 LLM을 호출하면 결정론이 깨집니다."
        )

    llm = get_llm()
    if llm is None:
        return None
    try:
        result = llm.with_structured_output(schema).invoke(prompt)
    except Exception:
        return None
    if result is None:
        return None

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result
