// FIXTURE — 실데이터 아님.
// 단, 삼성전자(005930) 감성 점수와 기사 제목은 실제 기사에서 집계했다. 자동 생성 파일이므로 직접 고치지 않는다.
// 생성: python frontend/scripts/build_sentiment_fixture.py --scorer finbert --daily-log <전수 배치 stderr 로그>
//       (backend value_pipeline news_agent와 같은 규칙)
// 원천: backend/analysis/text/data/processed/news_corpus.csv, 2025-10-29 ~ 2025-12-31 중 관련 기사가 있는 64일, 채점 8920건
// 감성 백엔드: kr-finbert (snunlp/KR-FinBert-SC), 기사 텍스트 = 제목 + 본문 앞 1000자
// N07 임계: 일별 감성 변화량 |Δ| 63개의 상위 10% 분위수(p90, inclusive 보간) = 0.3443
// 20일 창: 2025-12-02 ~ 2025-12-21. |Δ| >= p90인 가장 늦은 날로 끝나게 실제 날짜 구간을 골랐다.
//   마지막 날 |Δ| = 0.3942 (2025-12-20 +0.2095 → 2025-12-21 +0.6037)
// 코퍼스 기간이 화면의 예측 기준일(2025-10-02)보다 뒤다. 기간 정렬은 실데이터 연동 때 맞춘다.

import type { SentimentSeries } from "./index";

export const SENTIMENT_SHIFT_P90 = 0.3443;

export const SAMSUNG_SENTIMENT: SentimentSeries = {
  "days": [
    {
      "date": "2025-12-02",
      "score": 0.4096,
      "articleCount": 200
    },
    {
      "date": "2025-12-03",
      "score": 0.4806,
      "articleCount": 182
    },
    {
      "date": "2025-12-04",
      "score": 0.2929,
      "articleCount": 169
    },
    {
      "date": "2025-12-05",
      "score": 0.2199,
      "articleCount": 60
    },
    {
      "date": "2025-12-06",
      "score": 0.2966,
      "articleCount": 21
    },
    {
      "date": "2025-12-07",
      "score": 0.4217,
      "articleCount": 74
    },
    {
      "date": "2025-12-08",
      "score": 0.4138,
      "articleCount": 107
    },
    {
      "date": "2025-12-09",
      "score": 0.4095,
      "articleCount": 178
    },
    {
      "date": "2025-12-10",
      "score": 0.3015,
      "articleCount": 125
    },
    {
      "date": "2025-12-11",
      "score": 0.3465,
      "articleCount": 167
    },
    {
      "date": "2025-12-12",
      "score": 0.468,
      "articleCount": 188
    },
    {
      "date": "2025-12-13",
      "score": 0.3971,
      "articleCount": 22
    },
    {
      "date": "2025-12-14",
      "score": 0.3463,
      "articleCount": 88
    },
    {
      "date": "2025-12-15",
      "score": 0.2369,
      "articleCount": 200
    },
    {
      "date": "2025-12-16",
      "score": 0.2554,
      "articleCount": 146
    },
    {
      "date": "2025-12-17",
      "score": 0.5362,
      "articleCount": 116
    },
    {
      "date": "2025-12-18",
      "score": 0.1613,
      "articleCount": 200
    },
    {
      "date": "2025-12-19",
      "score": 0.4688,
      "articleCount": 146
    },
    {
      "date": "2025-12-20",
      "score": 0.2095,
      "articleCount": 14
    },
    {
      "date": "2025-12-21",
      "score": 0.6037,
      "articleCount": 55
    }
  ],
  "headlines": [
    {
      "date": "2025-12-21",
      "title": "[기고] 반도체 공정 화공약품 전문  업황 수혜 '기대'",
      "press": "무등일보"
    },
    {
      "date": "2025-12-21",
      "title": "HBM4 승부수 삼성전자, 엔비디아가 품질 테스트서 가장 좋은 평가",
      "press": "한국일보"
    },
    {
      "date": "2025-12-21",
      "title": "중남미 데이터센터 증가에 삼성, 냉난방공조 시장 공략",
      "press": "서울경제"
    }
  ]
};
