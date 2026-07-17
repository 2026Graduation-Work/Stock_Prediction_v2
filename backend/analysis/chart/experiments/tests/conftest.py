# ruff: noqa: I001

import sys
from pathlib import Path


CHART_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CHART_DIR))

# 실행 스크립트는 ``python train.py`` 형태도 지원하므로 형제 모듈 import를 쓴다.
# 테스트에서도 패키지 import와 직접 실행 import를 모두 해석할 수 있게 한다.
EXPERIMENTS_DIR = CHART_DIR / "experiments"
sys.path.insert(0, str(EXPERIMENTS_DIR))
