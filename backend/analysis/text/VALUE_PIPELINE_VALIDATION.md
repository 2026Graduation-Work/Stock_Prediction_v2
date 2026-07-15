# value_pipeline 출력 검증 기준

> **대상**: 이 파이프라인을 수정하거나 출력을 데이터셋에 넣으려는 사람/에이전트.
> **상위 규칙**: `AGENTS.md` (아키텍처 원칙). 이 문서는 그 원칙을 value_pipeline에
> 적용한 **검증 절차**이며, 규칙 본문을 중복 정의하지 않는다.

행 하나라도 이 기준을 어기면 **데이터셋에 넣지 않는다.** 오염된 행 하나가 없는 것보다 나쁘다 —
없으면 결측으로 처리되지만, 오염된 행은 모델이 학습해버린다.

---

## 1. 실행

```bash
cd backend/analysis/text
python -m value_pipeline.run --ticker 005930 --name 삼성전자 --date 2022-06-15
```

**필수 `.env` 키**

| 키 | 필수 | 용도 |
|---|---|---|
| `DART_API_KEY` | **필수** | 재무제표. 없으면 exit 2 (재무 없이 시그널을 만들지 않음) |
| `GEMINI_API_KEY` | 선택 | 뉴스 관련성 라벨링·이벤트 추출·근거 문장. 없으면 규칙 기반 |

**환경변수**

| 변수 | 기본 | 의미 |
|---|---|---|
| `USE_FINBERT` | `1` | `0`이면 39단어 사전 폴백 — **데이터셋 구축 시 절대 금지** |
| `LLM_REPLAY_ONLY` | `0` | `1`이면 LLM 캐시 미스가 에러 — **백테스트 재생 시 반드시 `1`** |

**종료 코드**

| 코드 | 의미 |
|---|---|
| 0 | 정상 + 검증 통과 |
| 2 | 재무 확보 실패 → 시그널 생성 거부 (`FinancialsUnavailableError`) |
| 3 | 실행은 됐으나 **검증 실패** → 이 행을 쓰지 말 것 |

출력: `{ticker}_{date}.json` (cwd 기준). `--out`으로 변경 가능.

---

## 2. PASS/FAIL 기준

### 2.1 스키마 계약

최상위 키가 **정확히** 다음 21개여야 한다. 추가도 누락도 FAIL.

```
ticker, date, company_name,
news_sentiment, news_impact_score, news_sentiment_std, news_staleness,
key_events, article_count, article_count_raw,
financial_health_score, valuation_score, financial_metrics, financial_fiscal_year,
composite_score, value_investment_signal, confidence, reasoning,
news_source, financial_source, validation
```

**되살아나면 안 되는 필드**: `data_quality`, `sentiment_backend`, `llm_used`, `social_*`, `sentiment_divergence`

확인: `test_value_signal_field_contract`

### 2.2 결정론 — 가장 중요

**같은 입력을 두 번 돌리면 `reasoning`·`key_events`를 뺀 모든 값이 같아야 한다.**

```bash
python -m value_pipeline.run --ticker 005930 --name 삼성전자 --date 2022-06-15 --out /tmp/a.json
python -m value_pipeline.run --ticker 005930 --name 삼성전자 --date 2022-06-15 --out /tmp/b.json
diff <(jq 'del(.reasoning)' /tmp/a.json) <(jq 'del(.reasoning)' /tmp/b.json)   # 차이 없어야 함
```

> ⚠️ **반드시 `.env`에 `GEMINI_API_KEY`가 있는 상태로 확인할 것.**
> 키가 없으면 LLM 경로 자체가 안 돌아 검증이 무의미하다. 실제로 이 함정에 빠진 적이 있다 —
> `test_run_pipeline_is_deterministic`이 CI에서만 초록이었고(`.env` 없음), 로컬에선 계속 실패했다.
> 테스트는 `agents.structured`를 patch해서 헤르메틱하게 만들었다. 환경변수 patch로는 안 된다:
> `config.load_dotenv()`가 import 시점에 `.env`를 주입하고, `SETTINGS`는 frozen dataclass,
> `get_llm()`은 `lru_cache`라 무력하다.

확인: `test_llm_text_cannot_change_any_score`, `test_run_pipeline_is_deterministic`

### 2.3 Point-in-time (룩어헤드 없음)

| 검사 | 기준 |
|---|---|
| `financial_fiscal_year` | `collectors.select_fiscal_year(date)`와 일치. `date`가 4/1 이후면 `date.year - 1`, 이전이면 `date.year - 2` |
| 뉴스 날짜 | 모든 기사가 기준일 당일 (`validation_agent`가 자동 검사) |
| staleness 비교군 | 기준일 **이전** 기사만 (`collect_prior_news`) |

근거: 사업보고서 법정 제출기한은 사업연도 종료(12/31) 후 90일 → 익년 3/31. 따라서 4/1부터
직전 사업연도 보고서가 공시돼 있다.

**실제로 났던 사고**: `_fetch_dart_financials`가 `date`를 무시하고 `dt.date.today().year - 1`을
써서, 2022-06-15 요청에 **FY2025 재무 + 2022년 주가**를 섞었다(4년 룩어헤드). `roe: 0.1036`이
삼성전자 FY2022 실제값(≈0.157)이 아닌 것이 증거였다. 수정 후 `roe: 0.1309` = FY2021 실제값.

확인: `test_select_fiscal_year_is_point_in_time`, `test_select_fiscal_year_does_not_depend_on_today`,
`test_fetch_dart_financials_uses_point_in_time_fiscal_year`, `test_validation_catches_lookahead_fiscal_year`

### 2.4 자기감사 (화이트박스)

**행 안의 모든 숫자를 그 행만 보고 재계산할 수 있어야 한다.** 이게 화이트박스 원칙의 구체적 형태다.

```
composite  = clip(valuation_score*0.6 + financial_health_score*0.4
                  + news_sentiment*(news_impact_score/10)*2, 0, 10)
signal     = band(composite)   # 8.0↑ STRONG_BUY, 6.5↑ BUY, 4.5↑ HOLD, 3.0↑ SELL, 그 외 STRONG_SELL
confidence = clip(0.5 + 0.125*real_sources - 0.15*news_sentiment_std
                  + 0.2*|composite-5|/5, 0.2, 0.95)
             # real_sources = news_source, financial_source 중 'sample'이 아닌 개수
```

계산값과 출력이 다르면 FAIL. `news_impact_score`·`article_count`를 출력에 남기는 이유가 이것이다 —
빼면 재계산이 불가능해진다.

확인: `test_row_is_self_auditing`

### 2.5 출처 (HITL: 근거·출처 항상 표시)

| 필드 | 기대값 | 아니면 |
|---|---|---|
| `news_source` | `bigkinds` | `naver*`는 과거 날짜 조회가 불안정 → 백테스트엔 부적합 |
| `financial_source` | `dart` | `sample`이면 **FAIL** — `sample_data/`는 존재하지 않으므로 이 값이 나오면 코드가 거짓말을 하는 것 |
| `key_events[].news_ids` | 비어있지 않음 | 비면 출처 없는 이벤트 = 환각 의심 (`validation.warnings`에 기록됨) |

### 2.6 값 범위

| 필드 | 범위 |
|---|---|
| `news_sentiment` | [-1, 1] |
| `news_impact_score` | [1, 10] 정수 |
| `news_sentiment_std` | ≥ 0 |
| `news_staleness` | [0, 1] |
| `financial_health_score`, `valuation_score`, `composite_score` | [0, 10] |
| `confidence` | [0.2, 0.95] |
| `value_investment_signal` | STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL |
| `article_count` | > 0 (0이면 FAIL — 2.8 참조) |

### 2.7 감성 백엔드 — 런 간 혼용 금지

**KR-FinBERT와 39단어 사전 폴백은 점수 스케일이 비교 불가능하다.** 여러 런을 모아 데이터셋을
만들 때 섞이면 조용한 regime break가 생긴다. 출력에 백엔드가 안 남으므로(피처로 무의미해서 뺐다)
**런 단위로 고정하고 기록할 것.**

```python
from value_pipeline.sentiment import score_texts
_, backend = score_texts(["삼성전자 실적 개선"])
assert backend == "kr-finbert"   # 데이터셋 구축 전 필수 확인
```

`torch`/`transformers` 미설치 시 조용히 lexicon으로 폴백한다. `requirements.txt`에 필수로 넣은 이유다.

### 2.8 결측 vs 0 구분

`news_sentiment == 0.0`은 **'중립'과 '기사 없음' 둘 다**를 의미한다 — `aggregate([])`가 `(0.0, 0.0)`을
반환하기 때문이고, `news_sentiment_std`도 양쪽 0.0이다. `article_count`만이 둘을 구분한다.

- `article_count == 0` → **FAIL.** `news_sentiment=0.0`은 관측이 아니라 날조다.
- 재무 지표 전부 결측 → **FAIL.** 점수가 기본값으로 채워진 것이다.

**실제로 났던 사고**: 재무 결측 시 `valuation_score`가 3.0(결측을 적자로 오인) · `health_score`가
5.0 → composite 3.8 → **confidence 0.548의 `SELL`과 그걸 정당화하는 유창한 LLM 근거문**이 나왔다.
중립 HOLD가 아니라 그럴듯한 가짜 매도 신호였다.

확인: `test_validation_catches_zero_articles`, `test_valuation_missing_data_is_not_treated_as_loss`

### 2.9 validation 블록

`validation.ok == false`면 **행을 쓰지 말 것** (run.py가 exit 3). `validation.warnings`는 치명적이진
않지만 확인 후 넘어갈 것.

`validation_agent`가 검사하는 것:

| # | 검사 | 잡는 버그 |
|---|---|---|
| 1 | 회계 항등식 `자산 ≈ 부채 + 자본` (허용오차 0.5%) | `_DART_MAP`이 first-wins라 **연결(CFS)/별도(OFS) 재무제표 혼입** 가능 — 이걸 잡는 유일한 검사 |
| 2 | 시가총액 상식 범위 (1e9~1e16원) | 발행주식수·주가 단위 오류. `per×eps≈price` 같은 검사는 **동어반복**이라 쓰지 말 것 — `compute_metrics`가 `per=price/eps`로 계산하므로 항상 참이다 |
| 3 | 지표 상식 범위 | `_band`가 **조용히 saturate**한다 — PER 300만이 나와도 최저 점수만 줄 뿐 거부하지 않는다. **하한도 중요**: 발행주식수 과소 → EPS 폭증 → PER이 0에 수렴 |
| 4 | 파생 정합성 (유동자산 ≤ 자산총계 등) | `_altman_z`가 결측을 `0.0`으로 강제(`or 0.0`)해 Z를 조용히 과소평가 |
| 5 | 뉴스 날짜 정렬 | point-in-time 위반 |
| 6 | 회계연도 vs 기준일 | 룩어헤드 |
| 7 | 결측 vs 0 | 2.8 |
| 8 | 이벤트 그라운딩 | LLM 환각 (warning) |
| 9 | 과대 필터 (10% 미만 잔존) | 관련성 필터 오작동 (warning) |
| 10 | 상한 유실 | 관련 기사가 임의로 버려짐 (warning) |

---

## 3. 금지 패턴

이 코드베이스에서 아래를 발견하면 **고치고 회귀 테스트를 추가할 것.**

### 3.1 LLM이 점수 경로에 개입

AGENTS.md: *"점수 산출은 100% 결정론(같은 입력→같은 출력). LLM은 설명 텍스트 생성에만."*

원칙 문제만이 아니다. **LLM은 이미 그 뉴스를 읽었고 그 다음에 주가가 어떻게 됐는지도 안다.**
Gao·Jiang·Yan (2025)은 LLM 예측의 룩어헤드를 Lookahead Propensity로 측정했는데, 블룸버그
헤드라인 → 익일 수익률에서 **명백한 알파의 약 37%가 암기(memorization)**였다. 학습 컷오프 이후
구간에선 그 효과가 통계적으로 사라졌다(플라시보 테스트). 삼성전자는 한국 대형주라 LAP가 최대다.

**그리고 캐싱·그라운딩·NLI 어느 것도 이걸 못 막는다.** 캐시는 유출된 예측을 완벽히 재현
가능하게 만들 뿐이고, 그라운딩은 유출된 추론이 실제 문장을 인용한다고 확인해줄 뿐이다.
**재현 가능한 것과 타당한 것은 다르다.** 환각은 잡음이라 백테스트를 나쁘게 만들지만, 암기는
in-sample에만 존재하는 신호라 백테스트를 좋아 보이게 만들고 실전에서 사라진다.

**구조적 방어**: `_NewsLabels`·`_RelevanceLabel`·`_Reason` 어느 스키마에도 **점수 필드를 두지 말 것.**
LLM 출력 계약에 점수가 없으면 실수로 다시 연결할 수 없다.
확인: `test_news_labels_schema_has_no_score_field`

### 3.2 `today()` 기반 회계연도

`dt.date.today()`가 재무·뉴스 선택에 등장하면 룩어헤드다. 기준일 `date`에서 파생할 것.

### 3.3 결측을 값으로 취급

`per is None`을 적자로 단정하기, `else 5.0` 기본값으로 조용히 메우기, `or 0.0`으로 결측을 0으로
강제하기. 결측은 결측으로 전파하고 검증에서 잡아라.

### 3.4 예외 조용히 삼키기

`except Exception: pass` / `data = None`. 최소한 `warnings.warn`. DART 실패가 완전히 보이지 않아
가짜 SELL이 나온 원인이었다.

### 3.5 LLM 크리틱으로 검증

**검증자를 LLM으로 만들지 말 것.** Huang et al. (ICLR 2024): 외부 피드백 없는 자기교정은
모든 벤치마크에서 성능을 떨어뜨렸다 — GSM8K 75.9→74.7, **CommonSenseQA 75.8→41.8**.
멀티에이전트 토론(83.2%)이 단순 self-consistency(85.3%)보다 못했다. LLM 판사는 자기 출력에
유리한 건 94.5%, 불리한 건 42.5%만 맞힌다. 원인은 **저perplexity(친숙한) 텍스트 선호**라
매끄러운 보도자료를 어색하지만 진짜 새로운 기사보다 높게 친다 — 원하는 신호의 정반대다.

자기교정이 실제로 작동하는 경우는 **외부 피드백**(도구·규칙·검증기)뿐이다. 그래서
`validation_agent`는 100% 규칙 기반이다.

### 3.6 벡터 DB / RAG를 같은 날 기사에

**실측**: 최악의 날(2022-10-27, 182건)이 본문 포함 **58k 토큰**. `gemini-2.5-flash` 컨텍스트는
**1M** — 6%다. 한 달 전체(1,798건 ≈ 620k)도 들어간다. 빅카인즈가 본문을 200자로 잘라줘서
청킹 문제조차 없다. 벡터 DB는 `torch`+임베딩 모델+faiss/chromadb를 끌고 와서 **컨텍스트에
통째로 들어가는 걸 골라낸다.** 오버엔지니어링이다.

시간축 검색(직전 기사 대비 신선도)은 다르며, 그건 `staleness.py`가 TF-IDF 없이 단어 중복률로 한다.

---

## 4. 설계 근거 — 왜 이렇게 돼 있나

측정으로 결판난 것들이라, 바꾸려면 재측정부터 할 것.

### 4.1 LLM은 요약이 아니라 관련성 필터에 쓴다

빅카인즈 키워드 검색이라 무관 기사가 섞인다. 2022-06-15(삼성전자 52주 신저가일) 실측:

| | 감성 |
|---|---|
| 전체 30건 | **+0.0429** ← 긍정 (틀림) |
| 무관 8건 제외 (22건) | **−0.1230** ← 부정 (맞음) |

**부호가 뒤집힌다.** 범인은 `구미대-희망디딤돌 업무협약`(+1.000), `제일기획 NFT`(+0.995),
`두산 반도체 투자`(+0.985), `미래에셋 ELW 상장`(+0.976), 그리고 `[공개] 오늘 아침 "폭등 예정"
종목 공개합니다` 주식 리딩방 스팸. FinBERT 판정은 **전부 맞다** — 삼성전자 기사가 아닐 뿐이다.

반면 **본문 200자 중간 절단은 감성에 영향이 없다**: 2022 전수 19,549건 중 82.4%가 문장 중간에
끊기지만, FinBERT raw vs 완전문장-트리밍 **상관 0.9995**, 평균 절대차 0.0047, 엔트로피 0.054 vs
0.048(둘 다 매우 낮음 = 혼란스러워하지 않음). 제목+본문 최대 324자로 FinBERT 창(512토큰≈340자)에
**100% 들어간다**(초과 0건).

**관련성 0.166(부호 반전) vs 절단 0.005 — 35배.** 그래서 LLM을 요약이 아니라 라벨링에 쓴다.
요약은 231자를 압축하는 게 아니라 버리는 것이고, 잘린 서술어는 LLM도 모르므로 극성을
**지어낼**(=메모리제이션 오염) 위험만 있다.

비용도 반대다: 기사별 요약은 10년 백테스트에 ~109,500 콜, 하루치 배치 라벨링은 연 365콜 +
content-hash 캐시로 재실행 0콜.

### 4.2 결정론은 모델이 아니라 인터페이스 경계에서 확보한다

`temperature=0`으로도 LLM은 결정론이 아니다 — 서버가 함께 배치하는 요청 수에 따라 커널 결과가
달라지고(batch invariance) 이건 통제 밖이다. 그래서 `llm.structured`가 content-hash로 출력을
동결한다. 캐시 키에 프롬프트·모델·스키마·파라미터를 **전부** 넣어야 한다 — 프롬프트가 빠지면
프롬프트를 고쳐도 옛 답이 나오는 조용한 staleness가 생긴다.

프롬프트를 수정하면 `llm.PROMPT_VERSION`을 올릴 것.

**재생 중 캐시 미스는 하드 에러여야 한다**(`LLM_REPLAY_ONLY=1`). 캐시를 '속도 최적화'로 취급해
미스 시 조용히 LLM을 부르면 재생은 더 이상 결정론이 아니다.

부수 효과: 독점 모델은 은퇴하고, 은퇴한 모델의 출력은 복구 불가능하다. 몇 달 뒤 심사에서
방어해야 하는 산출물엔 캐시가 최적화가 아니라 **생존 조건**이다.

### 4.3 staleness는 Tetlock을 근사하는 게 아니라 그대로 구현한 것

Tetlock (2011), RFS 24(5): staleness = **직전 10건 기사와의 단어 중복률**. 주가는 stale news에
덜 반응하지만, stale news 당일 수익률이 **다음 주 수익률을 음(-)으로 예측**한다(반전). 개인투자자가
stale news에 더 공격적으로 거래하고, 개인 비중이 높은 종목일수록 반전이 크다.

행동재무학 논지에 직결된다 — 개인의 과잉반응이 일시적 가격 왜곡을 만든다는 게 결론이다.
임베딩을 안 쓰는 이유: 단어 중복률은 비전공자에게 두 기사를 나란히 보여주며 "이 뉴스의 82%가
3일 전 기사와 겹칩니다"라고 설명할 수 있다. 임베딩 코사인 0.87로는 못 한다.

---

## 5. 회귀 테스트 대응표

`pytest backend/analysis/text/ -v` (repo root). **`.env`가 있는 상태에서도 초록이어야 한다** —
CI엔 `.env`가 없어 헤르메틱성을 못 잡는다.

| 기준 | 테스트 |
|---|---|
| 2.1 스키마 계약 | `test_value_signal_field_contract` |
| 2.2 결정론 | `test_llm_text_cannot_change_any_score`, `test_run_pipeline_is_deterministic`, `test_news_impact_score_is_deterministic_regardless_of_llm` |
| 2.3 point-in-time | `test_select_fiscal_year_is_point_in_time`, `test_select_fiscal_year_does_not_depend_on_today`, `test_fetch_dart_financials_uses_point_in_time_fiscal_year`, `test_validation_catches_lookahead_fiscal_year`, `test_validation_catches_misaligned_news_date` |
| 2.4 자기감사 | `test_row_is_self_auditing` |
| 2.5 출처 | `test_key_events_carry_source_news_ids`, `test_load_daily_news_emits_news_id_for_grounding`, `test_validation_warns_on_ungrounded_event` |
| 2.8 결측 vs 0 | `test_validation_catches_zero_articles`, `test_valuation_missing_data_is_not_treated_as_loss`, `test_collect_financials_raises_when_no_data` |
| 2.9 validation | `test_validation_passes_on_consistent_data`, `test_validation_catches_accounting_identity_violation`, `test_validation_catches_implausible_metric`, `test_validation_result_reaches_output` |
| 3.1 LLM 점수 개입 | `test_news_labels_schema_has_no_score_field` |
| 4.1 관련성 필터 | `test_relevance_filter_excludes_unrelated_articles`, `test_relevance_filter_falls_back_to_rule_without_llm`, `test_relevance_filter_never_drops_everything` |
| 4.3 staleness | `test_staleness_identical_article_is_fully_stale`, `test_staleness_new_article_is_fresh`, `test_staleness_is_deterministic` |

---

## 6. 알려진 한계 (문서화만, 미해결)

발표·리뷰에서 먼저 밝힐 것. 숨기면 신뢰를 잃고, 밝히면 오히려 점수를 얻는다.

1. **빅카인즈 20,000행 export 상한.** 삼성전자는 연 20,000건을 넘는 해가 많아 1년 단위로
   받으면 **최신순 정렬 때문에 연초가 잘린다.** 2022 파일(19,549건)만 우연히 온전하다.
   6개월 단위로 나눠 받을 것. `find_news_workbook`은 **파일명만** 보고 판단하므로
   잘린 파일도 커버한다고 주장한다 — 파일을 새로 받으면 실제 최소/최대 일자를 직접 확인할 것.
2. **DART 정정공시.** DART는 해당 사업연도의 *최신 정정본*을 반환하므로, 기준일 이후 제출된
   정정공시는 여전히 새어든다. `select_fiscal_year`는 보고서 **연도**만 통제한다(2차 오차).
3. **LLM 메모리제이션.** 3.1 참조. 점수 경로에서 LLM을 뺀 것이 주 방어책이지만, 관련성
   라벨링에도 이론상 잔존한다("이 기사가 삼성전자 사업에 관한 것인가"는 미래 수익률을 알아야
   답할 수 있는 질문이 아니라 노출이 작다). **모델 학습 컷오프와 백테스트 구간을 함께 명시할 것.**
4. **`_DART_MAP` 미매핑 항목.** `operating_cashflow`, `interest_expense`, `cash`, `ebitda`가
   매핑에 없어 `interest_coverage`는 DART 경로에서 **항상 결측**이고 `ev_ebitda`는 영업이익으로
   근사한다(둘 다 `FinancialMetrics`에서 제외되므로 출력엔 영향 없음).
5. **업종 평균 PER/PBR 부재.** `sector_per`/`sector_pbr`은 `sample_data/`에서 오는데 그 디렉터리가
   없어 항상 `None` → `valuation_score`가 절대 기준 밴드로 계산된다. 동종업계 대비가 아니다.
