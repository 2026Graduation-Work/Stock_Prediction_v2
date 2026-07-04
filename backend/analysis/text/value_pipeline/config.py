"""환경설정. 모든 키는 선택사항이며, 없으면 샘플/규칙 기반으로 동작한다.

.env 파일(있으면 자동 로드)에 다음을 넣으면 실데이터로 전환된다:
    GEMINI_API_KEY=...          # https://aistudio.google.com (무료 티어)
    DART_API_KEY=...            # https://opendart.fss.or.kr (무료)
    NAVER_CLIENT_ID=...         # https://developers.naver.com (검색 API, 무료)
    NAVER_CLIENT_SECRET=...
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:  # .env 자동 로드 (없으면 무시)
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # python-dotenv 미설치 시
    pass


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None = field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))
    dart_api_key: str | None = field(default_factory=lambda: os.getenv("DART_API_KEY"))
    naver_client_id: str | None = field(default_factory=lambda: os.getenv("NAVER_CLIENT_ID"))
    naver_client_secret: str | None = field(
        default_factory=lambda: os.getenv("NAVER_CLIENT_SECRET")
    )

    # Gemini 무료 티어 권장 모델 (1M 컨텍스트, JSON 모드, 한국어 우수)
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    # 한국어 금융 감성 특화 모델 (HuggingFace, 무료)
    finbert_model: str = field(
        default_factory=lambda: os.getenv("FINBERT_MODEL", "snunlp/KR-FinBert-SC")
    )
    use_finbert: bool = field(default_factory=lambda: os.getenv("USE_FINBERT", "1") != "0")

    news_lookback_days: int = 3
    price_lookback_days: int = 120

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_dart(self) -> bool:
        return bool(self.dart_api_key)

    @property
    def has_naver(self) -> bool:
        return bool(self.naver_client_id and self.naver_client_secret)


SETTINGS = Settings()
