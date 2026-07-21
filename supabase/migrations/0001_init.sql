-- SignalLab MVP database schema.
-- Paste this file into the Supabase SQL Editor, or run it with `supabase db reset`.

create table if not exists public.users (
  id text primary key,
  auth_user_id uuid unique references auth.users (id) on delete cascade,
  display_name text not null,
  avatar_label text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.stocks (
  code text primary key,
  name text not null,
  market text not null check (market in ('KOSPI', 'KOSDAQ')),
  risk_grade smallint not null check (risk_grade between 1 and 5),
  risk_flags text[] not null default '{}',
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint stocks_risk_flags_valid check (
    risk_flags <@ array[
      'spac',
      'managed_stock',
      'low_liquidity',
      'penny_stock',
      'high_volatility',
      'preferred_stock'
    ]::text[]
  )
);

create table if not exists public.ips_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id text not null unique references public.users (id) on delete cascade,
  session_id text not null,
  surveyed_at timestamptz not null,
  profile_type text not null check (profile_type in ('stable', 'aggressive')),
  max_risk_tier smallint not null check (max_risk_tier between 1 and 5),
  risk_score smallint not null check (risk_score between 0 and 100),
  fomo_score smallint not null check (fomo_score between 0 and 100),
  horizon_score smallint not null check (horizon_score between 0 and 100),
  risk_tolerance double precision not null check (risk_tolerance between 0 and 1),
  time_horizon_months integer not null check (time_horizon_months >= 0),
  liquidity_need_ratio double precision not null check (liquidity_need_ratio between 0 and 1),
  target_return_annual double precision not null,
  investment_experience_years double precision not null check (investment_experience_years >= 0),
  fomo_index double precision not null check (fomo_index between 0 and 1),
  panic_sell_tendency double precision not null check (panic_sell_tendency between 0 and 1),
  herding_score double precision not null check (herding_score between 0 and 1),
  self_confidence double precision not null check (self_confidence between 0 and 1),
  current_market_anxiety double precision not null check (current_market_anxiety between 0 and 1),
  overheating_caution double precision not null check (overheating_caution between 0 and 1),
  preferred_sectors text[] not null default '{}',
  free_text_raw text not null default '',
  extracted_signals jsonb not null default '{}'::jsonb,
  conflict_with_survey boolean not null default false,
  confidence_per_field jsonb not null default '{}'::jsonb,
  target_ticker text,
  investment_amount_krw bigint not null check (investment_amount_krw >= 0),
  action_intent text not null check (
    action_intent in ('buy_consideration', 'sell_consideration', 'hold_consideration')
  ),
  market_regime_hint text,
  benchmark_index text,
  schema_version text not null default '1.0.0' check (schema_version = '1.0.0'),
  source text not null default 'profiling_block' check (source = 'profiling_block'),
  confidence double precision check (confidence between 0 and 1),
  profile_payload jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.avoided_assets (
  user_id text not null references public.users (id) on delete cascade,
  asset_type text not null check (
    asset_type in (
      'spac',
      'managed_stock',
      'low_liquidity',
      'penny_stock',
      'high_volatility',
      'preferred_stock'
    )
  ),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, asset_type)
);

create table if not exists public.portfolio_holdings (
  user_id text not null references public.users (id) on delete cascade,
  stock_code text not null references public.stocks (code) on delete restrict,
  quantity integer not null check (quantity >= 0),
  avg_buy_price integer not null check (avg_buy_price >= 0),
  display_order smallint not null default 0,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, stock_code)
);

create table if not exists public.watchlist (
  user_id text not null references public.users (id) on delete cascade,
  stock_code text not null,
  display_order smallint not null default 0,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, stock_code)
);

create table if not exists public.predictions (
  id uuid primary key default gen_random_uuid(),
  stock_code text not null references public.stocks (code) on delete cascade,
  prediction_date date not null,
  data_asof date,
  model_type text not null check (model_type in ('stable', 'aggressive')),
  horizon text check (horizon in ('h5', 'h10', 'h20')),
  prob_up double precision not null check (prob_up between 0 and 1),
  rank_percentile double precision not null check (rank_percentile between 0 and 1),
  signal_light text not null check (
    signal_light in ('strong_positive', 'positive', 'neutral', 'negative', 'strong_negative')
  ),
  return_low double precision not null,
  return_high double precision not null,
  return_ci_level double precision,
  calibration_bucket text not null,
  bucket_hit_rate double precision not null check (bucket_hit_rate between 0 and 1),
  similar_case_count integer,
  uncertainty double precision,
  horizon_h5 text check (horizon_h5 in ('up', 'flat', 'down')),
  horizon_h10 text check (horizon_h10 in ('up', 'flat', 'down')),
  horizon_h20 text check (horizon_h20 in ('up', 'flat', 'down')),
  horizon_agreement text check (horizon_agreement in ('aligned', 'mixed', 'conflict')),
  factor_exposures jsonb not null default '{}'::jsonb,
  benchmark_index text,
  expected_holding_days integer,
  schema_version text not null default '1.0.0' check (schema_version = '1.0.0'),
  source text not null default 'chart_block' check (source = 'chart_block'),
  model_version text not null,
  prediction_hash text,
  disclaimer text,
  is_recommended boolean not null default false,
  is_holding_alert boolean not null default false,
  caution text,
  display_order smallint not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (stock_code, prediction_date, model_type)
);

create table if not exists public.prediction_features (
  prediction_id uuid not null references public.predictions (id) on delete cascade,
  feature text not null,
  label_ko text not null,
  contribution double precision not null,
  display_order smallint not null default 0,
  created_at timestamptz not null default now(),
  primary key (prediction_id, feature)
);

create table if not exists public.market_status (
  status_date date primary key,
  condition text not null check (condition in ('stable', 'caution', 'high_volatility')),
  volatility_score smallint not null check (volatility_score between 0 and 100),
  volume_score smallint not null check (volume_score between 0 and 100),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_users_auth_user_id on public.users (auth_user_id);
create index if not exists idx_stocks_risk_flags on public.stocks using gin (risk_flags);
create index if not exists idx_predictions_dashboard
  on public.predictions (model_type, prediction_date desc, display_order);
create index if not exists idx_portfolio_holdings_user_order
  on public.portfolio_holdings (user_id, display_order);

alter table public.users enable row level security;
alter table public.ips_profiles enable row level security;
alter table public.avoided_assets enable row level security;
alter table public.portfolio_holdings enable row level security;
alter table public.watchlist enable row level security;
alter table public.stocks enable row level security;
alter table public.predictions enable row level security;
alter table public.prediction_features enable row level security;
alter table public.market_status enable row level security;

-- Remove both the original broad policies and these policies before recreating them.
-- This keeps the migration safe to rerun after an earlier MVP schema was applied.
do $drop_policies$
declare
  table_name text;
  policy_suffix text;
begin
  foreach table_name in array array[
    'users',
    'ips_profiles',
    'avoided_assets',
    'portfolio_holdings',
    'watchlist',
    'stocks',
    'predictions',
    'prediction_features',
    'market_status'
  ]
  loop
    foreach policy_suffix in array array[
      '_anon_select',
      '_authenticated_insert',
      '_authenticated_update',
      '_public_select',
      '_owner_select',
      '_owner_insert',
      '_owner_update'
    ]
    loop
      execute format(
        'drop policy if exists %I on public.%I',
        table_name || policy_suffix,
        table_name
      );
    end loop;
  end loop;
end
$drop_policies$;

-- Market and model outputs are public read-only data. Backend ingestion uses
-- service_role, which bypasses RLS; browser clients cannot mutate these rows.
create policy stocks_public_select on public.stocks
  for select to anon, authenticated using (true);
create policy predictions_public_select on public.predictions
  for select to anon, authenticated using (true);
create policy prediction_features_public_select on public.prediction_features
  for select to anon, authenticated using (true);
create policy market_status_public_select on public.market_status
  for select to anon, authenticated using (true);

-- A user row is visible and writable only to the linked Supabase Auth account.
create policy users_owner_select on public.users
  for select to authenticated using (auth.uid() = auth_user_id);
create policy users_owner_insert on public.users
  for insert to authenticated with check (auth.uid() = auth_user_id);
create policy users_owner_update on public.users
  for update to authenticated
  using (auth.uid() = auth_user_id)
  with check (auth.uid() = auth_user_id);

create policy ips_profiles_owner_select on public.ips_profiles
  for select to authenticated using (
    exists (
      select 1 from public.users as app_user
      where app_user.id = ips_profiles.user_id
        and app_user.auth_user_id = auth.uid()
    )
  );
create policy ips_profiles_owner_insert on public.ips_profiles
  for insert to authenticated with check (
    exists (
      select 1 from public.users as app_user
      where app_user.id = ips_profiles.user_id
        and app_user.auth_user_id = auth.uid()
    )
  );
create policy ips_profiles_owner_update on public.ips_profiles
  for update to authenticated
  using (
    exists (
      select 1 from public.users as app_user
      where app_user.id = ips_profiles.user_id
        and app_user.auth_user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from public.users as app_user
      where app_user.id = ips_profiles.user_id
        and app_user.auth_user_id = auth.uid()
    )
  );

create policy avoided_assets_owner_select on public.avoided_assets
  for select to authenticated using (
    exists (
      select 1 from public.users as app_user
      where app_user.id = avoided_assets.user_id
        and app_user.auth_user_id = auth.uid()
    )
  );
create policy avoided_assets_owner_insert on public.avoided_assets
  for insert to authenticated with check (
    exists (
      select 1 from public.users as app_user
      where app_user.id = avoided_assets.user_id
        and app_user.auth_user_id = auth.uid()
    )
  );
create policy avoided_assets_owner_update on public.avoided_assets
  for update to authenticated
  using (
    exists (
      select 1 from public.users as app_user
      where app_user.id = avoided_assets.user_id
        and app_user.auth_user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from public.users as app_user
      where app_user.id = avoided_assets.user_id
        and app_user.auth_user_id = auth.uid()
    )
  );

create policy portfolio_holdings_owner_select on public.portfolio_holdings
  for select to authenticated using (
    exists (
      select 1 from public.users as app_user
      where app_user.id = portfolio_holdings.user_id
        and app_user.auth_user_id = auth.uid()
    )
  );
create policy portfolio_holdings_owner_insert on public.portfolio_holdings
  for insert to authenticated with check (
    exists (
      select 1 from public.users as app_user
      where app_user.id = portfolio_holdings.user_id
        and app_user.auth_user_id = auth.uid()
    )
  );
create policy portfolio_holdings_owner_update on public.portfolio_holdings
  for update to authenticated
  using (
    exists (
      select 1 from public.users as app_user
      where app_user.id = portfolio_holdings.user_id
        and app_user.auth_user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from public.users as app_user
      where app_user.id = portfolio_holdings.user_id
        and app_user.auth_user_id = auth.uid()
    )
  );

create policy watchlist_owner_select on public.watchlist
  for select to authenticated using (
    exists (
      select 1 from public.users as app_user
      where app_user.id = watchlist.user_id
        and app_user.auth_user_id = auth.uid()
    )
  );
create policy watchlist_owner_insert on public.watchlist
  for insert to authenticated with check (
    exists (
      select 1 from public.users as app_user
      where app_user.id = watchlist.user_id
        and app_user.auth_user_id = auth.uid()
    )
  );
create policy watchlist_owner_update on public.watchlist
  for update to authenticated
  using (
    exists (
      select 1 from public.users as app_user
      where app_user.id = watchlist.user_id
        and app_user.auth_user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from public.users as app_user
      where app_user.id = watchlist.user_id
        and app_user.auth_user_id = auth.uid()
    )
  );

grant usage on schema public to anon, authenticated;

revoke all on table
  public.users,
  public.ips_profiles,
  public.avoided_assets,
  public.portfolio_holdings,
  public.watchlist
from anon, authenticated;

revoke all on table
  public.stocks,
  public.predictions,
  public.prediction_features,
  public.market_status
from anon, authenticated;

grant select, insert, update on table
  public.users,
  public.ips_profiles,
  public.avoided_assets,
  public.portfolio_holdings,
  public.watchlist
to authenticated;

grant select on table
  public.stocks,
  public.predictions,
  public.prediction_features,
  public.market_status
to anon, authenticated;
