// PLACEHOLDER — 사전 기반 300건 표본. FinBERT 전수 결과로 교체 대기 중.
// FIXTURE — 실데이터 아님.
// 단, 삼성전자(005930) 감성 점수와 기사 제목은 실제 기사에서 집계했다. 자동 생성 파일이므로 직접 고치지 않는다.
// 생성: python frontend/scripts/build_sentiment_fixture.py --scorer dictionary --limit 300
//       (backend value_pipeline news_agent와 같은 규칙)
// 원천: backend/analysis/text/data/processed/news_corpus.csv, 2025-10-29 ~ 2025-12-31 중 관련 기사가 있는 64일, 채점 253건
// 감성 백엔드: dictionary (value_pipeline.sentiment 사전 폴백 39단어), 기사 텍스트 = 제목 + 본문 앞 1000자
// N07 임계: 일별 감성 변화량 |Δ| 63개의 상위 10% 분위수(p90, inclusive 보간) = 0.7
// 코퍼스 기간이 화면의 예측 기준일(2025-10-02)보다 뒤다. 기간 정렬은 실데이터 연동 때 맞춘다.

import type { SentimentSeries } from "./index";

export const SENTIMENT_SHIFT_P90 = 0.7;

export const SAMSUNG_SENTIMENT: SentimentSeries = {
  "days": [
    {
      "date": "2025-12-12",
      "score": 0.0,
      "articleCount": 4
    },
    {
      "date": "2025-12-13",
      "score": 0.0,
      "articleCount": 4
    },
    {
      "date": "2025-12-14",
      "score": 0.25,
      "articleCount": 4
    },
    {
      "date": "2025-12-15",
      "score": 0.25,
      "articleCount": 4
    },
    {
      "date": "2025-12-16",
      "score": 0.0,
      "articleCount": 4
    },
    {
      "date": "2025-12-17",
      "score": 0.5,
      "articleCount": 4
    },
    {
      "date": "2025-12-18",
      "score": 0.5,
      "articleCount": 4
    },
    {
      "date": "2025-12-19",
      "score": 0.5,
      "articleCount": 4
    },
    {
      "date": "2025-12-20",
      "score": 0.5,
      "articleCount": 4
    },
    {
      "date": "2025-12-21",
      "score": 0.0,
      "articleCount": 4
    },
    {
      "date": "2025-12-22",
      "score": 0.75,
      "articleCount": 4
    },
    {
      "date": "2025-12-23",
      "score": 0.25,
      "articleCount": 4
    },
    {
      "date": "2025-12-24",
      "score": 0.25,
      "articleCount": 4
    },
    {
      "date": "2025-12-25",
      "score": 0.75,
      "articleCount": 4
    },
    {
      "date": "2025-12-26",
      "score": 0.0,
      "articleCount": 4
    },
    {
      "date": "2025-12-27",
      "score": 1.0,
      "articleCount": 4
    },
    {
      "date": "2025-12-28",
      "score": 1.0,
      "articleCount": 4
    },
    {
      "date": "2025-12-29",
      "score": 0.25,
      "articleCount": 4
    },
    {
      "date": "2025-12-30",
      "score": 0.5,
      "articleCount": 4
    },
    {
      "date": "2025-12-31",
      "score": 0.5,
      "articleCount": 4
    }
  ],
  "headlines": [
    {
      "date": "2025-12-31",
      "title": "끝까지 날았다 삼전 SK하이닉스 역대 최고가로 ‘피날레’",
      "press": "국민일보"
    },
    {
      "date": "2025-12-31",
      "title": "[사설] 코스피 질주 이어가려면 기업 역동성 더 살려야",
      "press": "국민일보"
    },
    {
      "date": "2025-12-31",
      "title": "JY ‘전장 드라이브’ 삼성 반도체, BMW 차세대 전기차 탑재",
      "press": "국민일보"
    }
  ]
};
