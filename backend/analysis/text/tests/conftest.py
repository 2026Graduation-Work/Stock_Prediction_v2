import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(autouse=True)
def _clear_collector_caches():
    """collectors의 프로세스 캐시(lru_cache)가 테스트 간에 새지 않게 비운다.

    DART/FDR 캐시는 배치 성능용인데, 테스트에서는 이전 테스트의 대역(fake) 응답이
    캐시에 남아 다음 테스트로 흘러드는 오염 경로가 된다.
    """
    from analysis.text.value_pipeline import collectors

    collectors._fetch_dart_by_fiscal_year.cache_clear()
    collectors._price_history.cache_clear()
    yield
    collectors._fetch_dart_by_fiscal_year.cache_clear()
    collectors._price_history.cache_clear()
