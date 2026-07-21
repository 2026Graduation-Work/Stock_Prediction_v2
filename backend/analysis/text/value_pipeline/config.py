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
    # 재생(replay) 모드: LLM 캐시 미스를 에러로 만든다. 백테스트 데이터셋을 만들 때
    # 켜면, 재생 중 LLM이 호출되어 결정론이 깨지는 일을 구조적으로 막는다.
    llm_replay_only: bool = field(
        default_factory=lambda: os.getenv("LLM_REPLAY_ONLY", "0") != "0"
    )

    news_lookback_days: int = 3
    price_lookback_days: int = 120
    # 뉴스 감성에 쓸 최대 기사 수 (관련성 라벨링 후 적용).
    # 병리적인 날을 막는 안전 상한일 뿐, 실제로는 걸리지 않아야 한다 —
    # 감성은 평균이라 관련 기사가 많을수록 추정이 정확해지고, FinBERT는 로컬이라
    # 비용이 사실상 없다. 상한에 걸리면 '어느 기사를 버릴지'가 임의 선택이 되어
    # 관련성 필터로 없앤 노이즈가 되살아난다(실측: 2022-06-15 관련 37건 중 7건 유실).
    max_daily_articles: int = 200
    # staleness 계산 시 비교할 직전 기사 수 (Tetlock 2011은 10건)
    staleness_lookback_articles: int = 10
    # 직전 기사 10건을 채우기 위해 거슬러 올라갈 최대 일수
    staleness_lookback_days: int = 7

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
