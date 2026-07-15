"""뉴스 신선도(staleness) 측정 — 결정론·화이트박스.

Tetlock (2011), "All the News That's Fit to Reprint: Do Investors React to Stale
Information?", Review of Financial Studies 24(5), 1481-1512.

구성을 그대로 따른다: staleness = 해당 종목의 '직전 10건' 기사와의 단어 중복률.
Tetlock의 발견:
- 주가는 오래된(stale) 뉴스에 덜 반응한다.
- 그런데 stale news 당일 수익률은 다음 주 수익률을 음(-)으로 예측한다 (반전).
- 개인투자자가 stale news에 더 공격적으로 거래하며, 개인 비중이 높은 종목일수록
  반전이 크다 → 개인의 과잉반응이 일시적 가격 왜곡을 만든다.

행동재무학 기반 심리 지수라는 프로젝트 논지에 직결되는 피처다.

임베딩·벡터DB를 쓰지 않는 이유: 비교 대상이 '직전 10건'이라 후보군이 애초에 작고,
단어 중복률은 비전공자에게 두 기사를 나란히 보여주며 "이 뉴스의 82%가 3일 전
기사와 겹칩니다"라고 설명할 수 있다(화이트박스). 임베딩 코사인 0.87로는 못 한다.
"""
from __future__ import annotations

import re

# 한글·영문·숫자 2자 이상 토큰. 조사가 붙어도 어간이 겹치면 잡히도록 단순 유지.
_TOKEN = re.compile(r"[가-힣]{2,}|[A-Za-z]{2,}|\d+")


def tokenize(text: str) -> set[str]:
    """중복률 계산용 토큰 집합."""
    return set(_TOKEN.findall(text or ""))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _overlap(cur: set[str], prev: set[str]) -> float:
    """Tetlock의 '겹치는 단어 비율' — 현재 기사 기준 피복률.

    Jaccard가 아니라 비대칭 피복률을 쓴다: 짧은 속보가 긴 기존 기사를 그대로
    베낀 경우 Jaccard는 길이 차 때문에 낮게 나오지만, 이 기사가 새 정보를
    담았는지가 궁금한 것이므로 '현재 기사의 단어 중 몇 %가 기존에 있었나'가 맞다.
    """
    if not cur:
        return 0.0
    return len(cur & prev) / len(cur)


def staleness_score(current: list[str], previous: list[str]) -> float:
    """0.0(완전히 새로움) ~ 1.0(전부 기존 기사와 겹침).

    current  : 그날 기사 텍스트들 (제목+본문)
    previous : 직전 N건 기사 텍스트들 (오래된 순/최신순 무관)

    각 현재 기사에 대해 '직전 기사 전체 어휘'와의 피복률을 구해 평균한다.
    previous가 비면 0.0 (비교 대상 없음 = 신선하다고 보지 않고 중립 처리).
    """
    if not current or not previous:
        return 0.0
    prev_vocab: set[str] = set()
    for t in previous:
        prev_vocab |= tokenize(t)
    if not prev_vocab:
        return 0.0
    scores = [_overlap(tokenize(t), prev_vocab) for t in current]
    return round(sum(scores) / len(scores), 4)


def pairwise_max_similarity(current: list[str], previous: list[str]) -> float:
    """가장 유사한 개별 기사와의 Jaccard 최대값 — '이 뉴스는 재탕인가' 직접 판정용.

    staleness_score가 어휘 전체 대비 평균이라면 이건 '단 한 건이라도 거의 같은
    기사가 있었나'를 본다. 근거 제시(화이트박스)에 쓰기 좋다.
    """
    if not current or not previous:
        return 0.0
    prev_toks = [tokenize(t) for t in previous]
    best = 0.0
    for c in current:
        ct = tokenize(c)
        for p in prev_toks:
            best = max(best, _jaccard(ct, p))
    return round(best, 4)
