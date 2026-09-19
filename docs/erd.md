# Supabase ERD

`supabase/migrations/` 0001~0003 기준. 스키마가 바뀌면 이 문서와 `frontend/lib/types.ts`를 함께 고친다.

> 0003(schema_version `1.1.0` 허용)은 아직 미적용이다. 적용 전 담당자 확인이 필요하다.
> 8축은 별도 컬럼 없이 `profile_payload.style_axes`에 저장하므로 0003 없이도 앱은 동작한다(8축만 null).

```mermaid
erDiagram
  auth_users ||--o| users : "auth_user_id"
  users ||--o| ips_profiles : "user_id (unique)"
  users ||--o{ avoided_assets : "user_id"
  users ||--o{ portfolio_holdings : "user_id"
  users ||--o{ watchlist : "user_id"
  stocks ||--o{ portfolio_holdings : "stock_code"
  stocks ||--o{ predictions : "stock_code"
  predictions ||--o{ prediction_features : "prediction_id"

  users {
    text id PK
    uuid auth_user_id UK,FK
    text display_name
    text avatar_label
    timestamptz created_at
    timestamptz updated_at
  }

  stocks {
    text code PK
    text name
    text market "KOSPI | KOSDAQ"
    smallint risk_grade "1 매우 위험 ~ 5 매우 안전"
    text_array risk_flags "avoided_assets enum과 동일"
    boolean is_active
    timestamptz created_at
    timestamptz updated_at
  }

  ips_profiles {
    uuid id PK
    text user_id UK,FK
    text session_id
    timestamptz surveyed_at
    text profile_type "stable | aggressive"
    smallint max_risk_tier "1~5, 저장 시 profile_type에서 자동 파생"
    smallint risk_score "0~100"
    smallint fomo_score "0~100"
    smallint horizon_score "0~100"
    float8 risk_tolerance
    integer time_horizon_months
    float8 liquidity_need_ratio
    float8 target_return_annual
    float8 investment_experience_years
    float8 fomo_index
    float8 panic_sell_tendency
    float8 herding_score
    float8 self_confidence
    float8 current_market_anxiety
    float8 overheating_caution
    text_array preferred_sectors
    text free_text_raw
    jsonb extracted_signals
    boolean conflict_with_survey
    jsonb confidence_per_field
    text target_ticker
    bigint investment_amount_krw
    text action_intent
    text market_regime_hint
    text benchmark_index
    text schema_version "1.0.0 | 1.1.0 (0003)"
    text source "profiling_block"
    float8 confidence
    jsonb profile_payload "profiling_output 원본. v1.1이면 style_axes 포함"
    timestamptz created_at
    timestamptz updated_at
  }

  avoided_assets {
    text user_id PK,FK
    text asset_type PK "spac | managed_stock | low_liquidity | penny_stock | high_volatility | preferred_stock"
    boolean is_active
    timestamptz created_at
    timestamptz updated_at
  }

  portfolio_holdings {
    text user_id PK,FK
    text stock_code PK,FK
    integer quantity
    integer avg_buy_price
    smallint display_order
    boolean is_active
    timestamptz created_at
    timestamptz updated_at
  }

  watchlist {
    text user_id PK,FK
    text stock_code PK "stocks FK 없음"
    smallint display_order
    boolean is_active
    timestamptz created_at
    timestamptz updated_at
  }

  predictions {
    uuid id PK
    text stock_code FK
    date prediction_date
    date data_asof
    text model_type "stable | aggressive"
    text horizon "h5 | h10 | h20"
    float8 prob_up
    float8 rank_percentile
    text signal_light
    float8 return_low
    float8 return_high
    float8 return_ci_level
    text calibration_bucket
    float8 bucket_hit_rate
    integer similar_case_count
    float8 uncertainty
    text horizon_h5
    text horizon_h10
    text horizon_h20
    text horizon_agreement
    jsonb factor_exposures
    text benchmark_index
    integer expected_holding_days
    text schema_version "1.0.0"
    text source "chart_block"
    text model_version
    text prediction_hash
    text disclaimer
    boolean is_recommended
    boolean is_holding_alert
    text caution
    smallint display_order
    timestamptz created_at
    timestamptz updated_at
  }

  prediction_features {
    uuid prediction_id PK,FK
    text feature PK
    text label_ko
    float8 contribution
    smallint display_order
    timestamptz created_at
  }

  market_status {
    date status_date PK
    text condition "stable | caution | high_volatility"
    smallint volatility_score
    smallint volume_score
    jsonb index_quotes "0002"
    timestamptz created_at
    timestamptz updated_at
  }
```

## `ips_profiles.profile_payload.style_axes` 형태

`schema/profiling_output.schema.json` v1.1 `style_axes` ↔ `frontend/lib/types.ts` `StyleAxes`.

```json
{
  "assessment_mode": "quick | detailed",
  "axes": [
    { "axis_id": "turnover", "ratio": -0.25, "confidence": 0.95, "answered_count": 3, "question_count": 3 }
  ]
}
```

- `axes`는 8축을 모두 담는다: `market_participation`, `loss_tolerance`, `turnover`, `concentration`,
  `rule_adherence`, `information_reliance`, `urgency`, `drawdown_reaction`.
- `ratio` -1~+1, `confidence` 0~1. 극성은 `frontend/lib/profiling/style-questions.json` `axes`가 SSOT다.
- `rule_adherence`는 -1이 사전 규칙 준수, +1이 상황별 재량이다. 이름과 극성 방향이 반대로 읽히니 주의한다.
