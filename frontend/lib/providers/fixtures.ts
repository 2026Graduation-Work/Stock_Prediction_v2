// FIXTURE — 실데이터 아님.
// 삼성전자(005930)·현대차(005380) 두 종목만 둔다. 값은 시드 고정 PRNG와 손으로 정한 상수다(수급은 실데이터로 옮김).
// 실데이터 구현체로 교체하면 이 파일을 지운다.

import type {
  ContributionSignalInput,
  SentimentSeries,
} from "./index";
import { SUPPLY_SNAPSHOT } from "./demo-snapshot.ts";
import { SAMSUNG_SENTIMENT } from "./sentiment-fixture.ts";

const PREDICTION_AS_OF = "2025-12-30"; // 데모 기준일(실데이터 스냅샷과 같은 날)

// mulberry32. 시드가 같으면 항상 같은 수열이다.
function seeded(seed: number) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const signedUnit = (random: () => number) => random() * 2 - 1;

// ponytail: 평일 휴장일은 예시 수급 구간(2025-12 20영업일)에 걸린 날만 둔다.
// 실데이터 연동 시 날짜를 데이터에서 받으므로 이 표는 지운다.
const KRX_WEEKDAY_HOLIDAYS = new Set(["2025-12-25"]);

export function businessDaysEndingAt(end: string, count: number): string[] {
  const days: string[] = [];
  const cursor = new Date(`${end}T00:00:00Z`);
  while (days.length < count) {
    const date = cursor.toISOString().slice(0, 10);
    const weekday = cursor.getUTCDay();
    if (weekday !== 0 && weekday !== 6 && !KRX_WEEKDAY_HOLIDAYS.has(date)) days.unshift(date);
    cursor.setUTCDate(cursor.getUTCDate() - 1);
  }
  return days;
}

// 현대차 감성은 합성이다. 삼성전자 실데이터와 같은 날짜 축에 PRNG 점수를 둔다.
const hyundaiRandom = seeded(5380_2);
export const HYUNDAI_SENTIMENT: SentimentSeries = {
  days: SAMSUNG_SENTIMENT.days.map(({ date }) => ({
    date,
    score: Math.round((0.12 + signedUnit(hyundaiRandom) * 0.22) * 10000) / 10000,
    articleCount: 18 + Math.floor(hyundaiRandom() * 30),
  })),
  // 합성 기사 제목은 실제 사건처럼 읽히지 않도록 합성임을 제목에 드러낸다.
  headlines: [1, 2, 3].map((index) => ({
    date: SAMSUNG_SENTIMENT.days.at(-1)?.date ?? PREDICTION_AS_OF,
    title: `[합성 픽스처] 현대차 관련 기사 제목 ${index}`,
    press: "합성 픽스처",
  })),
};

// 원점수 weight는 부호 없는 크기. provider가 합 100으로 정규화한다.
// direction은 그 근거가 신호를 어느 쪽으로 밀었는지(+1 오르는 쪽, -1 내리는 쪽)다.
// 수급 근거는 실제 순매수(SUPPLY_SNAPSHOT) 20일 합계의 부호에서 계산하고, 나머지는 예시 신호(긍정)와 같은 쪽으로 둔다.
const flowDirection = (code: string, key: "foreign" | "institution"): 1 | -1 =>
  SUPPLY_SNAPSHOT[code].reduce((sum, day) => sum + day[key], 0) >= 0 ? 1 : -1;

// description은 신호의 정의만 적는다. 다른 카드 수치와 어긋나는 사실 주장을 넣지 않는다.
export const CONTRIBUTION_FIXTURE: Record<string, ContributionSignalInput[]> = {
  "005930": [
    {
      signal: "ma_cross_20_60",
      label: "20일·60일 이동평균 위치",
      category: "technical",
      weight: 31,
      description: "단기 추세선이 중기 추세선 위에 있는지와 그 기간을 봅니다.",
    },
    {
      signal: "news_sentiment_14d",
      label: "최근 2주 뉴스 감성",
      category: "sentiment",
      weight: 22,
      description: "관련 기사 감성 점수의 2주 평균과 방향을 봅니다.",
    },
    {
      signal: "operating_profit_surprise",
      label: "영업이익 시장 예상치 대비",
      category: "financial",
      weight: 20,
      description: "직전 분기 영업이익이 발표 전 시장 예상치와 얼마나 달랐는지 봅니다.",
    },
    {
      signal: "foreign_flow_20d",
      label: "외국인 20일 누적 순매수",
      category: "supply",
      weight: 15,
      direction: flowDirection("005930", "foreign"),
      description: "최근 20영업일 외국인 순매수 합계의 크기와 부호를 봅니다.",
    },
    {
      signal: "volume_ratio_20d",
      label: "20거래일 거래량 비율",
      category: "technical",
      weight: 12,
      description: "최근 20거래일 평균 거래량을 직전 60거래일 평균과 비교합니다.",
    },
  ],
  "005380": [
    {
      signal: "momentum_60d",
      label: "60일 모멘텀",
      category: "technical",
      weight: 34,
      description: "최근 60거래일 수익률을 전체 종목과 비교한 순위를 봅니다.",
    },
    {
      signal: "institution_flow_20d",
      label: "기관 20일 누적 순매수",
      category: "supply",
      weight: 22,
      direction: flowDirection("005380", "institution"),
      description: "최근 20영업일 기관 순매수 합계의 크기와 부호를 봅니다.",
    },
    {
      signal: "news_sentiment_14d",
      label: "최근 2주 뉴스 감성",
      category: "sentiment",
      weight: 18,
      description: "관련 기사 감성 점수의 2주 평균과 방향을 봅니다.",
    },
    {
      signal: "volume_ratio_20d",
      label: "20거래일 거래량 비율",
      category: "technical",
      weight: 14,
      description: "최근 20거래일 평균 거래량을 직전 60거래일 평균과 비교합니다.",
    },
    {
      signal: "pbr_band",
      label: "PBR 과거 범위 내 위치",
      category: "financial",
      weight: 12,
      description: "현재 PBR이 과거 5년 범위의 어디쯤인지 봅니다.",
    },
  ],
};

// 실제 공시값이 아니다. DART 재무 연동 시 교체한다.
// 시장 전체 종목 중 최근 60거래일 변동성 백분위(1 = 가장 큼). 시장 분포 데이터가 없어 정한 값이다.
// 대형주는 소형주를 포함한 시장 전체 기준으로 중간 부근이다. 넛지 발화와 무관하게 정했다.
export const VOLATILITY_PERCENTILE_FIXTURE: Record<string, number> = {
  "005930": 0.48,
  "005380": 0.35,
};
