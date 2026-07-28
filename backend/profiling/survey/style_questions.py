"""8축 투자스타일 진단 문항 은행 — profiling 블록.

기존 `questions.py`(객관식 5 + 자유텍스트 1)는 문항 하나가 축 하나에 대응해
응답 일관성을 볼 수 없었다. 여기서는 축당 복수 문항을 두어 축 점수와 함께
**신뢰도(응답 일관성)** 를 산출할 수 있게 한다.

설계 규칙
- 리커트 5점. 응답값 1~5를 -2~+2로 중심화한다.
- 축마다 역채점 문항(`direction == -1`)을 최소 1개 둔다. 무조건 동의하는
  응답 습관(묵종 경향)을 잡아내야 신뢰도가 의미를 갖는다.
- `quick=True` 문항만 모으면 빠른 진단이 된다. 스코어링 규칙은 두 모드가 같다.
- 이 모듈은 데이터만 담는다. 계산은 `style_scoring.py`가 한다.
"""

from __future__ import annotations

from typing import Final

# 리커트 응답값 → 중심화 점수. 3(보통)이 0이 되도록 -3 한다.
LIKERT_OPTIONS: Final = (
    {"value": 1, "label": "전혀 그렇지 않다"},
    {"value": 2, "label": "그렇지 않다"},
    {"value": 3, "label": "보통이다"},
    {"value": 4, "label": "그렇다"},
    {"value": 5, "label": "매우 그렇다"},
)
LIKERT_NEUTRAL: Final = 3
LIKERT_EXTREME: Final = 2  # 중심화 후 절댓값 최대

# 8축. negative_label이 ratio 음수 쪽, positive_label이 양수 쪽이다.
# 이 부호 규약은 schema/profiling_output.schema.json의 style_axes와 같아야 한다.
AXES: Final = (
    {
        "id": "market_participation",
        "negative_label": "시장 수익률 참여",
        "positive_label": "내 목표 우선",
        "section": "시장과 내 목표",
        "help": "시장 전체 수익률을 따라가는 것이 중요한지, 내가 정한 목표 달성이 중요한지",
    },
    {
        "id": "loss_tolerance",
        "negative_label": "원금 보전",
        "positive_label": "수익 기회",
        "section": "손실을 버틸 수 있는 정도",
        "help": "원금이 줄어드는 것을 어디까지 견딜 수 있는지",
    },
    {
        "id": "holding_horizon",
        "negative_label": "장기 보유",
        "positive_label": "단기 회전",
        "section": "보유 기간",
        "help": "한번 산 종목을 얼마나 오래 들고 갈 생각인지",
    },
    {
        "id": "concentration",
        "negative_label": "폭넓은 분산",
        "positive_label": "소수 집중",
        "section": "집중과 분산",
        "help": "몇 개 종목에 집중할지, 여러 자산에 나눌지",
    },
    {
        "id": "rule_adherence",
        "negative_label": "사전 규칙 준수",
        "positive_label": "상황별 재량",
        "section": "계획을 지키는 방식",
        "help": "미리 정한 기준을 지킬지, 상황에 따라 바꿀지",
    },
    {
        "id": "information_reliance",
        "negative_label": "본인 판단",
        "positive_label": "시장·타인 추종",
        "section": "판단의 근거",
        "help": "투자 판단을 직접 확인한 자료로 내리는지, 주변과 시장 분위기를 따르는지",
    },
    {
        "id": "urgency",
        "negative_label": "여유",
        "positive_label": "조급함",
        "section": "기회를 대하는 태도",
        "help": "지금 사지 않으면 놓친다는 조급함이 얼마나 큰지",
    },
    {
        "id": "drawdown_reaction",
        "negative_label": "하락 시 유지",
        "positive_label": "하락 시 이탈",
        "section": "하락에 대한 반응",
        "help": "가격이 떨어질 때 계획을 유지하는지, 정리하고 나오는지",
    },
)

AXIS_IDS: Final = tuple(axis["id"] for axis in AXES)

# 문항 은행. direction +1이면 동의할수록 positive_label 쪽, -1이면 negative_label 쪽이다.
# weight는 축 안에서의 상대 비중이며 기본 1이다.
STYLE_QUESTIONS: Final = (
    # ── market_participation ────────────────────────────────────────────────
    {
        "id": "mp01",
        "axis": "market_participation",
        "direction": 1,
        "weight": 1,
        "quick": True,
        "text": "내 투자 성과는 시장 지수보다 내가 정한 목표 금액에 도달했는지가 중요하다.",
    },
    {
        "id": "mp02",
        "axis": "market_participation",
        "direction": -1,
        "weight": 1,
        "quick": True,
        "text": "시장이 크게 오를 때 내 투자도 그만큼 따라가면 좋겠다.",
    },
    {
        "id": "mp03",
        "axis": "market_participation",
        "direction": -1,
        "weight": 1,
        "quick": True,
        "text": "투자 성과를 볼 때 코스피 같은 대표 지수와 비교해 보고 싶다.",
    },
    {
        "id": "mp04",
        "axis": "market_participation",
        "direction": 1,
        "weight": 1,
        "quick": False,
        "text": "시장이 어떻든 내가 정한 수익 목표만 채우면 만족한다.",
    },
    {
        "id": "mp05",
        "axis": "market_participation",
        "direction": -1,
        "weight": 1,
        "quick": False,
        "text": "여러 종목을 한 번에 담아 시장 전체를 따라가는 상품이 마음 편하다.",
    },
    # ── loss_tolerance ──────────────────────────────────────────────────────
    {
        "id": "lt01",
        "axis": "loss_tolerance",
        "direction": 1,
        "weight": 1,
        "quick": True,
        "text": "더 큰 수익을 위해서라면 원금이 줄어드는 기간도 견딜 수 있다.",
    },
    {
        "id": "lt02",
        "axis": "loss_tolerance",
        "direction": -1,
        "weight": 1,
        "quick": True,
        "text": "무엇보다 원금이 줄지 않는 것이 가장 중요하다.",
    },
    {
        "id": "lt03",
        "axis": "loss_tolerance",
        "direction": 1,
        "weight": 1,
        "quick": True,
        "text": "가격이 크게 흔들려도 기대 수익이 크다면 감수할 만하다.",
    },
    {
        "id": "lt04",
        "axis": "loss_tolerance",
        "direction": -1,
        "weight": 1,
        "quick": False,
        "text": "예금처럼 원금이 지켜지는 쪽이 마음이 편하다.",
    },
    {
        "id": "lt05",
        "axis": "loss_tolerance",
        "direction": 1,
        "weight": 1,
        "quick": False,
        "text": "손실이 나더라도 회복될 시간이 있다면 크게 걱정하지 않는다.",
    },
    # ── holding_horizon ─────────────────────────────────────────────────────
    {
        "id": "hh01",
        "axis": "holding_horizon",
        "direction": 1,
        "weight": 1,
        "quick": True,
        "text": "한번 산 종목도 몇 달 안에 정리하는 편이 낫다고 생각한다.",
    },
    {
        "id": "hh02",
        "axis": "holding_horizon",
        "direction": -1,
        "weight": 1,
        "quick": True,
        "text": "좋다고 판단한 종목은 몇 년이든 그대로 들고 가는 것이 맞다.",
    },
    {
        "id": "hh03",
        "axis": "holding_horizon",
        "direction": 1,
        "weight": 1,
        "quick": True,
        "text": "수익이 조금이라도 나면 빨리 실현하고 싶다.",
    },
    {
        "id": "hh04",
        "axis": "holding_horizon",
        "direction": -1,
        "weight": 1,
        "quick": False,
        "text": "이 투자금은 오랫동안 쓰지 않아도 괜찮다.",
    },
    {
        "id": "hh05",
        "axis": "holding_horizon",
        "direction": 1,
        "weight": 1,
        "quick": False,
        "text": "시장 흐름에 맞춰 자주 갈아타는 편이 유리하다고 본다.",
    },
    # ── concentration ───────────────────────────────────────────────────────
    {
        "id": "cd01",
        "axis": "concentration",
        "direction": 1,
        "weight": 1,
        "quick": True,
        "text": "확신이 서는 종목이라면 비중을 크게 실어도 괜찮다.",
    },
    {
        "id": "cd02",
        "axis": "concentration",
        "direction": -1,
        "weight": 1,
        "quick": True,
        "text": "종목을 여러 개로 나눠 담아야 마음이 놓인다.",
    },
    {
        "id": "cd03",
        "axis": "concentration",
        "direction": 1,
        "weight": 1,
        "quick": True,
        "text": "잘 아는 몇 개 종목에 집중하는 편이 낫다고 생각한다.",
    },
    {
        "id": "cd04",
        "axis": "concentration",
        "direction": -1,
        "weight": 1,
        "quick": False,
        "text": "업종과 지역을 골고루 나누는 것이 중요하다.",
    },
    {
        "id": "cd05",
        "axis": "concentration",
        "direction": 1,
        "weight": 1,
        "quick": False,
        "text": "분산을 많이 하면 수익이 희석된다고 느낀다.",
    },
    # ── rule_adherence ──────────────────────────────────────────────────────
    {
        "id": "ra01",
        "axis": "rule_adherence",
        "direction": 1,
        "weight": 1,
        "quick": True,
        "text": "미리 정한 원칙보다 그때그때의 상황 판단이 더 중요하다.",
    },
    {
        "id": "ra02",
        "axis": "rule_adherence",
        "direction": -1,
        "weight": 1,
        "quick": True,
        "text": "투자 전에 다시 점검할 기준을 정해 두고 그대로 지키고 싶다.",
    },
    {
        "id": "ra03",
        "axis": "rule_adherence",
        "direction": 1,
        "weight": 1,
        "quick": True,
        "text": "시장이 급하게 움직이면 정해둔 계획은 바꿀 수 있다고 본다.",
    },
    {
        "id": "ra04",
        "axis": "rule_adherence",
        "direction": -1,
        "weight": 1,
        "quick": False,
        "text": "정기적으로 비중을 점검하고 원래 계획대로 되돌리는 방식이 좋다.",
    },
    {
        "id": "ra05",
        "axis": "rule_adherence",
        "direction": 1,
        "weight": 1,
        "quick": False,
        "text": "규칙에 얽매이면 좋은 기회를 놓친다고 생각한다.",
    },
    # ── information_reliance ────────────────────────────────────────────────
    {
        "id": "ir01",
        "axis": "information_reliance",
        "direction": 1,
        "weight": 1,
        "quick": True,
        "text": "많은 사람이 사는 종목이라면 그럴 만한 이유가 있다고 생각한다.",
    },
    {
        "id": "ir02",
        "axis": "information_reliance",
        "direction": -1,
        "weight": 1,
        "quick": True,
        "text": "투자 결정은 내가 직접 확인한 자료로 내린다.",
    },
    {
        "id": "ir03",
        "axis": "information_reliance",
        "direction": 1,
        "weight": 1,
        "quick": True,
        "text": "커뮤니티나 영상에서 자주 언급되는 종목에 관심이 간다.",
    },
    {
        "id": "ir04",
        "axis": "information_reliance",
        "direction": -1,
        "weight": 1,
        "quick": False,
        "text": "남들이 뭐라 하든 내 판단이 서지 않으면 사지 않는다.",
    },
    {
        "id": "ir05",
        "axis": "information_reliance",
        "direction": 1,
        "weight": 1,
        "quick": False,
        "text": "주변에서 좋다고 하면 일단 살펴보게 된다.",
    },
    # ── urgency ─────────────────────────────────────────────────────────────
    {
        "id": "ug01",
        "axis": "urgency",
        "direction": 1,
        "weight": 1,
        "quick": True,
        "text": "지금 사지 않으면 기회를 놓칠 것 같아 마음이 급해질 때가 있다.",
    },
    {
        "id": "ug02",
        "axis": "urgency",
        "direction": -1,
        "weight": 1,
        "quick": True,
        "text": "좋은 기회는 앞으로도 또 온다고 생각한다.",
    },
    {
        "id": "ug03",
        "axis": "urgency",
        "direction": 1,
        "weight": 1,
        "quick": True,
        "text": "다른 사람이 크게 벌었다는 이야기를 들으면 초조해진다.",
    },
    {
        "id": "ug04",
        "axis": "urgency",
        "direction": -1,
        "weight": 1,
        "quick": False,
        "text": "매수 시점을 며칠 늦춰도 크게 상관없다고 본다.",
    },
    {
        "id": "ug05",
        "axis": "urgency",
        "direction": 1,
        "weight": 1,
        "quick": False,
        "text": "하루에도 여러 번 계좌를 확인하게 된다.",
    },
    # ── drawdown_reaction ───────────────────────────────────────────────────
    {
        "id": "dr01",
        "axis": "drawdown_reaction",
        "direction": 1,
        "weight": 1,
        "quick": True,
        "text": "손실이 커지면 일단 정리하고 지켜보고 싶어진다.",
    },
    {
        "id": "dr02",
        "axis": "drawdown_reaction",
        "direction": -1,
        "weight": 1,
        "quick": True,
        "text": "가격이 떨어져도 처음 판단이 그대로면 계속 들고 간다.",
    },
    {
        "id": "dr03",
        "axis": "drawdown_reaction",
        "direction": 1,
        "weight": 1,
        "quick": True,
        "text": "하락이 이어지면 밤에 잠이 잘 오지 않는다.",
    },
    {
        "id": "dr04",
        "axis": "drawdown_reaction",
        "direction": -1,
        "weight": 1,
        "quick": False,
        "text": "하락은 지나가는 과정이라고 받아들이는 편이다.",
    },
    {
        "id": "dr05",
        "axis": "drawdown_reaction",
        "direction": 1,
        "weight": 1,
        "quick": False,
        "text": "마이너스 수익률을 보면 빨리 벗어나고 싶다.",
    },
)

ASSESSMENT_MODES: Final = ("quick", "detailed")


def questions_for_mode(mode: str) -> tuple[dict, ...]:
    """진단 모드에 해당하는 문항만 원래 순서대로 돌려준다."""
    if mode not in ASSESSMENT_MODES:
        raise ValueError(f"mode must be one of {ASSESSMENT_MODES}")
    if mode == "detailed":
        return STYLE_QUESTIONS
    return tuple(question for question in STYLE_QUESTIONS if question["quick"])


# holding_horizon.ratio → time_horizon_months 구간표.
# schema의 style_axes 설명이 이 테이블을 SSOT로 지목한다.
# ratio가 작을수록(장기 보유) 개월 수가 커진다.
HOLDING_HORIZON_MONTH_RULES: Final = (
    {"max_ratio": -0.60, "months": 120},
    {"max_ratio": -0.20, "months": 60},
    {"max_ratio": 0.20, "months": 36},
    {"max_ratio": 0.60, "months": 18},
    {"max_ratio": 1.01, "months": 6},
)
