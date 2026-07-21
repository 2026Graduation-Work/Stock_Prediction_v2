"use client";

import type { ProfilingOutput } from "./types";
import { horizonScoreForMonths } from "./profiling-rules";
import { getSupabaseClient } from "./supabase";

export const PROFILE_STORAGE_KEY = "signallab.ips-profile.v1";
export const PROFILE_UPDATED_EVENT = "signallab:profile-updated";

export async function saveProfile(profile: ProfilingOutput): Promise<void> {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile));
  window.dispatchEvent(new Event(PROFILE_UPDATED_EVENT));

  const client = getSupabaseClient();
  if (!client) return;

  const { data, error: sessionError } = await client.auth.getSession();
  assertSupabaseResult(sessionError, "로그인 세션 확인");
  if (!data.session) return;

  const now = new Date().toISOString();
  const metadata = data.session.user.user_metadata;
  const displayName =
    typeof metadata.full_name === "string" && metadata.full_name.trim()
      ? metadata.full_name.trim()
      : profile.user_id;
  const avatarLabel = Array.from(displayName)[0] ?? "";

  const authUserId = data.session.user.id;
  const { data: existingUser, error: existingUserError } = await client
    .from("users")
    .select("id")
    .eq("auth_user_id", authUserId)
    .maybeSingle();
  assertSupabaseResult(existingUserError, "기존 사용자 확인");

  // Supabase Auth ID를 최초 DB 사용자 ID로 사용하고, 재설문 시 기존 ID를 재사용한다.
  const userId = (existingUser as { id: string } | null)?.id ?? authUserId;
  const storedProfile: ProfilingOutput = { ...profile, user_id: userId };
  const { error: userError } = await client.from("users").upsert(
    {
      id: userId,
      auth_user_id: authUserId,
      display_name: displayName,
      avatar_label: avatarLabel,
      updated_at: now,
    },
    { onConflict: "auth_user_id" },
  );
  assertSupabaseResult(userError, "사용자 저장");

  const investor = profile.investor_profile;
  const psychology = profile.psychological_state;
  const freeText = profile.free_text_signal;
  const context = profile.context;
  const { error: profileError } = await client.from("ips_profiles").upsert(
    {
      user_id: userId,
      session_id: profile.session_id,
      surveyed_at: profile.timestamp,
      profile_type: investor.profile_type,
      max_risk_tier: investor.profile_type === "stable" ? 4 : 2,
      risk_score: Math.round(investor.risk_tolerance * 100),
      fomo_score: Math.round(psychology.fomo_index * 100),
      horizon_score: horizonScoreForMonths(investor.time_horizon_months),
      risk_tolerance: investor.risk_tolerance,
      time_horizon_months: investor.time_horizon_months,
      liquidity_need_ratio: investor.liquidity_need_ratio,
      target_return_annual: investor.target_return_annual,
      investment_experience_years: investor.investment_experience_years,
      fomo_index: psychology.fomo_index,
      panic_sell_tendency: psychology.panic_sell_tendency,
      herding_score: psychology.herding_score,
      self_confidence: psychology.self_confidence,
      current_market_anxiety: psychology.current_market_anxiety,
      overheating_caution: psychology.overheating_caution,
      preferred_sectors: profile.constraints.preferred_sectors,
      free_text_raw: freeText.raw_text,
      extracted_signals: freeText.extracted_signals,
      conflict_with_survey: freeText.conflict_with_survey,
      confidence_per_field: profile.confidence_per_field,
      target_ticker: context.target_ticker ?? null,
      investment_amount_krw: context.investment_amount_krw,
      action_intent: context.action_intent,
      market_regime_hint: context.market_regime_hint ?? null,
      benchmark_index: context.benchmark_index ?? null,
      schema_version: profile.meta.schema_version,
      source: profile.meta.source,
      confidence: profile.meta.confidence,
      profile_payload: storedProfile,
      updated_at: now,
    },
    { onConflict: "user_id" },
  );
  assertSupabaseResult(profileError, "IPS 프로필 저장");

  const [avoidedReset, holdingsReset, watchlistReset] = await Promise.all([
    client
      .from("avoided_assets")
      .update({ is_active: false, updated_at: now })
      .eq("user_id", userId),
    client
      .from("portfolio_holdings")
      .update({ is_active: false, updated_at: now })
      .eq("user_id", userId),
    client
      .from("watchlist")
      .update({ is_active: false, updated_at: now })
      .eq("user_id", userId),
  ]);
  assertSupabaseResult(avoidedReset.error, "기존 회피 설정 비활성화");
  assertSupabaseResult(holdingsReset.error, "기존 보유 종목 비활성화");
  assertSupabaseResult(watchlistReset.error, "기존 관심 종목 비활성화");

  await Promise.all([
    upsertAvoidedAssets(profile, userId, now),
    upsertPortfolioHoldings(profile, userId, now),
    upsertWatchlist(profile, userId, now),
  ]);
}

async function upsertAvoidedAssets(
  profile: ProfilingOutput,
  userId: string,
  updatedAt: string,
): Promise<void> {
  if (!profile.constraints.avoided_assets.length) return;
  const client = getSupabaseClient();
  if (!client) return;
  const { error } = await client.from("avoided_assets").upsert(
    profile.constraints.avoided_assets.map((assetType) => ({
      user_id: userId,
      asset_type: assetType,
      is_active: true,
      updated_at: updatedAt,
    })),
    { onConflict: "user_id,asset_type" },
  );
  assertSupabaseResult(error, "회피 설정 저장");
}

async function upsertPortfolioHoldings(
  profile: ProfilingOutput,
  userId: string,
  updatedAt: string,
): Promise<void> {
  if (!profile.portfolio.holdings.length) return;
  const client = getSupabaseClient();
  if (!client) return;

  const tickers = profile.portfolio.holdings.map(({ ticker }) => ticker);
  const { data, error: stockError } = await client
    .from("stocks")
    .select("code")
    .in("code", tickers);
  assertSupabaseResult(stockError, "보유 종목 마스터 확인");
  const knownCodes = new Set(
    ((data ?? []) as { code: string }[]).map(({ code }) => code),
  );
  const rows = profile.portfolio.holdings.flatMap((holding, index) =>
    knownCodes.has(holding.ticker)
      ? [
          {
            user_id: userId,
            stock_code: holding.ticker,
            quantity: holding.quantity,
            avg_buy_price: holding.avg_buy_price,
            display_order: index + 1,
            is_active: true,
            updated_at: updatedAt,
          },
        ]
      : [],
  );
  if (!rows.length) return;

  const { error } = await client.from("portfolio_holdings").upsert(rows, {
    onConflict: "user_id,stock_code",
  });
  assertSupabaseResult(error, "보유 종목 저장");
}

async function upsertWatchlist(
  profile: ProfilingOutput,
  userId: string,
  updatedAt: string,
): Promise<void> {
  if (!profile.portfolio.watchlist.length) return;
  const client = getSupabaseClient();
  if (!client) return;
  const { error } = await client.from("watchlist").upsert(
    profile.portfolio.watchlist.map((stockCode, index) => ({
      user_id: userId,
      stock_code: stockCode,
      display_order: index + 1,
      is_active: true,
      updated_at: updatedAt,
    })),
    { onConflict: "user_id,stock_code" },
  );
  assertSupabaseResult(error, "관심 종목 저장");
}

function assertSupabaseResult(
  error: { message: string } | null,
  operation: string,
): asserts error is null {
  if (error) throw new Error(`${operation} 실패: ${error.message}`);
}

export function getSavedProfileSnapshot(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(PROFILE_STORAGE_KEY);
}

export function getServerProfileSnapshot(): null {
  return null;
}

export function subscribeToSavedProfile(onStoreChange: () => void) {
  if (typeof window === "undefined") return () => undefined;
  window.addEventListener("storage", onStoreChange);
  window.addEventListener(PROFILE_UPDATED_EVENT, onStoreChange);
  return () => {
    window.removeEventListener("storage", onStoreChange);
    window.removeEventListener(PROFILE_UPDATED_EVENT, onStoreChange);
  };
}

export function parseSavedProfile(serialized: string | null): ProfilingOutput | null {
  if (!serialized) return null;
  try {
    const parsed: unknown = JSON.parse(serialized);
    return isProfilingOutput(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function isProfilingOutput(value: unknown): value is ProfilingOutput {
  if (!isRecord(value)) return false;
  const investor = value.investor_profile;
  const psychology = value.psychological_state;
  const constraints = value.constraints;
  const meta = value.meta;
  if (
    !isRecord(investor) ||
    !isRecord(psychology) ||
    !isRecord(constraints) ||
    !isRecord(meta)
  ) {
    return false;
  }

  const validRiskFlags = new Set([
    "spac",
    "managed_stock",
    "low_liquidity",
    "penny_stock",
    "high_volatility",
    "preferred_stock",
  ]);
  return (
    typeof value.timestamp === "string" &&
    !Number.isNaN(Date.parse(value.timestamp)) &&
    typeof investor.risk_tolerance === "number" &&
    Number.isFinite(investor.risk_tolerance) &&
    typeof investor.time_horizon_months === "number" &&
    Number.isFinite(investor.time_horizon_months) &&
    (investor.profile_type === "stable" || investor.profile_type === "aggressive") &&
    typeof psychology.fomo_index === "number" &&
    Number.isFinite(psychology.fomo_index) &&
    Array.isArray(constraints.avoided_assets) &&
    constraints.avoided_assets.every(
      (asset) => typeof asset === "string" && validRiskFlags.has(asset),
    ) &&
    meta.schema_version === "1.0.0"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
