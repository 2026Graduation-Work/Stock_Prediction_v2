import type { SupabaseClient } from "@supabase/supabase-js";
import {
  avoidanceNotice,
  holdingAlerts,
  investorProfile,
  marketStatus,
  portfolioHoldings,
  recommendedStocks,
} from "./mock-data";
import {
  mapAvoidedAssetLabels,
  mapExcludedStocks,
  mapMarketStatus,
  mapPortfolioHolding,
  mapProfileSummary,
  mapRecommendedStock,
  toRiskFlags,
  type AvoidedAssetRow,
  type ExcludedStock,
  type IpsProfileRow,
  type MarketStatusRow,
  type PortfolioHoldingRow,
  type PredictionRow,
  type StockRow,
  type UserRow,
} from "./mappers";
import { getSupabaseClient } from "./supabase";
import type {
  InvestorProfileSummary,
  MarketStatus,
  PortfolioHolding,
  RecommendedStock,
} from "./types";

export const DEMO_USER_ID = "u_minji_001";

export interface ProfileQueryResult {
  profile: InvestorProfileSummary;
  avoidedLabels: string[];
  excludedStocks: ExcludedStock[];
}

interface ProfileSettingsRow {
  profile_type: "stable" | "aggressive";
  max_risk_tier: number;
}

interface ProfileSettings {
  profileType: "stable" | "aggressive";
  maxRiskTier: number;
  avoided: Set<string>;
}

const PREDICTION_COLUMNS =
  "stock_code,prediction_date,signal_light,rank_percentile,return_low,return_high,return_ci_level,bucket_hit_rate,similar_case_count,horizon_h5,horizon_h10,horizon_h20,horizon_agreement,caution,display_order" as const;

const STOCK_COLUMNS = "code,name,market,risk_grade,risk_flags";

export async function getMarketStatus(): Promise<MarketStatus> {
  return withFallback("market status", marketStatus, async (client) => {
    const { data, error } = await client
      .from("market_status")
      .select("status_date,condition,volatility_score,volume_score")
      .order("status_date", { ascending: false })
      .limit(1)
      .maybeSingle();
    assertQuery(error, "시장 상태 조회");
    if (!data) throw new Error("시장 상태 데이터가 없습니다.");
    return mapMarketStatus(data as MarketStatusRow);
  });
}

export async function getRecommendedStocks(
  userId = DEMO_USER_ID,
): Promise<RecommendedStock[]> {
  return withFallback("recommended stocks", recommendedStocks, async (client) => {
    const settings = await loadProfileSettings(client, userId);
    const { data, error } = await client
      .from("predictions")
      .select(PREDICTION_COLUMNS)
      .eq("model_type", settings.profileType)
      .eq("is_recommended", true)
      .order("prediction_date", { ascending: false })
      .order("display_order", { ascending: true });
    assertQuery(error, "추천 예측 조회");

    const predictions = latestDateRows((data ?? []) as PredictionRow[]);
    const stocks = await loadStocks(
      client,
      predictions.map(({ stock_code }) => stock_code),
    );
    const stockByCode = new Map(stocks.map((stock) => [stock.code, stock]));

    return predictions.flatMap((prediction) => {
      const stock = stockByCode.get(prediction.stock_code);
      if (
        !stock ||
        stock.risk_grade < settings.maxRiskTier ||
        toRiskFlags(stock.risk_flags).some((flag) => settings.avoided.has(flag))
      ) {
        return [];
      }
      return [mapRecommendedStock(prediction, stock)];
    });
  });
}

export async function getHoldingAlerts(
  userId = DEMO_USER_ID,
): Promise<RecommendedStock[]> {
  return withFallback("holding alerts", holdingAlerts, async (client) => {
    const settings = await loadProfileSettings(client, userId);
    const holdings = await loadHoldings(client, userId);
    if (!holdings.length) return [];

    const { data, error } = await client
      .from("predictions")
      .select(PREDICTION_COLUMNS)
      .eq("model_type", settings.profileType)
      .eq("is_holding_alert", true)
      .in(
        "stock_code",
        holdings.map(({ stock_code }) => stock_code),
      )
      .order("prediction_date", { ascending: false })
      .order("display_order", { ascending: true });
    assertQuery(error, "보유 종목 알림 조회");

    const predictions = latestRowsByStock((data ?? []) as PredictionRow[]);
    const stocks = await loadStocks(
      client,
      predictions.map(({ stock_code }) => stock_code),
    );
    const stockByCode = new Map(stocks.map((stock) => [stock.code, stock]));
    return predictions.flatMap((prediction) => {
      const stock = stockByCode.get(prediction.stock_code);
      return stock ? [mapRecommendedStock(prediction, stock)] : [];
    });
  });
}

export async function getPortfolio(
  userId = DEMO_USER_ID,
): Promise<PortfolioHolding[]> {
  return withFallback("portfolio", portfolioHoldings, async (client) => {
    const settings = await loadProfileSettings(client, userId);
    const holdings = await loadHoldings(client, userId);
    if (!holdings.length) return [];

    const codes = holdings.map(({ stock_code }) => stock_code);
    const [stocks, predictionResult] = await Promise.all([
      loadStocks(client, codes),
      client
        .from("predictions")
        .select(PREDICTION_COLUMNS)
        .eq("model_type", settings.profileType)
        .in("stock_code", codes)
        .order("prediction_date", { ascending: false }),
    ]);
    assertQuery(predictionResult.error, "포트폴리오 예측 조회");

    const stockByCode = new Map(stocks.map((stock) => [stock.code, stock]));
    const predictionByCode = new Map(
      latestRowsByStock((predictionResult.data ?? []) as PredictionRow[]).map(
        (prediction) => [prediction.stock_code, prediction],
      ),
    );

    return holdings.flatMap((holding) => {
      const stock = stockByCode.get(holding.stock_code);
      return stock
        ? [mapPortfolioHolding(holding, stock, predictionByCode.get(holding.stock_code))]
        : [];
    });
  });
}

export async function getProfile(
  userId = DEMO_USER_ID,
): Promise<ProfileQueryResult> {
  const fallback: ProfileQueryResult = {
    profile: investorProfile,
    avoidedLabels: avoidanceNotice.avoidedLabels,
    excludedStocks: avoidanceNotice.excludedStocks,
  };

  return withFallback("profile", fallback, async (client) => {
    const [userResult, profileResult, avoidedResult, stocks] = await Promise.all([
      client
        .from("users")
        .select("id,display_name,avatar_label")
        .eq("id", userId)
        .maybeSingle(),
      client
        .from("ips_profiles")
        .select(
          "user_id,surveyed_at,profile_type,max_risk_tier,risk_score,fomo_score,horizon_score",
        )
        .eq("user_id", userId)
        .maybeSingle(),
      client
        .from("avoided_assets")
        .select("asset_type")
        .eq("user_id", userId)
        .eq("is_active", true),
      loadStocks(client),
    ]);
    assertQuery(userResult.error, "사용자 조회");
    assertQuery(profileResult.error, "IPS 프로필 조회");
    assertQuery(avoidedResult.error, "회피 설정 조회");
    if (!userResult.data || !profileResult.data) {
      throw new Error("사용자 또는 IPS 프로필 데이터가 없습니다.");
    }

    const avoidedRows = (avoidedResult.data ?? []) as AvoidedAssetRow[];
    return {
      profile: mapProfileSummary(
        userResult.data as UserRow,
        profileResult.data as IpsProfileRow,
      ),
      avoidedLabels: mapAvoidedAssetLabels(avoidedRows),
      excludedStocks: mapExcludedStocks(stocks, avoidedRows),
    };
  });
}

async function loadProfileSettings(
  client: SupabaseClient,
  userId: string,
): Promise<ProfileSettings> {
  const [profileResult, avoidedResult] = await Promise.all([
    client
      .from("ips_profiles")
      .select("profile_type,max_risk_tier")
      .eq("user_id", userId)
      .maybeSingle(),
    client
      .from("avoided_assets")
      .select("asset_type")
      .eq("user_id", userId)
      .eq("is_active", true),
  ]);
  assertQuery(profileResult.error, "추천 설정 조회");
  assertQuery(avoidedResult.error, "추천 회피 설정 조회");
  if (!profileResult.data) throw new Error("추천에 사용할 IPS 프로필이 없습니다.");

  const profile = profileResult.data as ProfileSettingsRow;
  return {
    profileType: profile.profile_type,
    maxRiskTier: profile.max_risk_tier,
    avoided: new Set(
      ((avoidedResult.data ?? []) as AvoidedAssetRow[]).map(
        ({ asset_type }) => asset_type,
      ),
    ),
  };
}

async function loadStocks(
  client: SupabaseClient,
  codes?: string[],
): Promise<StockRow[]> {
  if (codes && codes.length === 0) return [];
  let query = client.from("stocks").select(STOCK_COLUMNS).eq("is_active", true);
  if (codes) query = query.in("code", [...new Set(codes)]);
  const { data, error } = await query;
  assertQuery(error, "종목 마스터 조회");
  return (data ?? []) as StockRow[];
}

async function loadHoldings(
  client: SupabaseClient,
  userId: string,
): Promise<PortfolioHoldingRow[]> {
  const { data, error } = await client
    .from("portfolio_holdings")
    .select("stock_code,display_order")
    .eq("user_id", userId)
    .eq("is_active", true)
    .order("display_order", { ascending: true });
  assertQuery(error, "보유 종목 조회");
  return (data ?? []) as PortfolioHoldingRow[];
}

function latestDateRows(rows: PredictionRow[]): PredictionRow[] {
  const latestDate = rows[0]?.prediction_date;
  return latestDate ? rows.filter(({ prediction_date }) => prediction_date === latestDate) : [];
}

function latestRowsByStock(rows: PredictionRow[]): PredictionRow[] {
  const latestByStock = new Map<string, PredictionRow>();
  for (const row of rows) {
    if (!latestByStock.has(row.stock_code)) latestByStock.set(row.stock_code, row);
  }
  return [...latestByStock.values()].sort(
    (left, right) =>
      left.display_order - right.display_order || left.stock_code.localeCompare(right.stock_code),
  );
}

async function withFallback<T>(
  label: string,
  fallback: T,
  query: (client: SupabaseClient) => Promise<T>,
): Promise<T> {
  const client = getSupabaseClient();
  if (!client) return fallback;
  try {
    return await query(client);
  } catch (error) {
    console.warn(`[Supabase fallback] ${label}:`, error);
    return fallback;
  }
}

function assertQuery(
  error: { message: string } | null,
  operation: string,
): asserts error is null {
  if (error) throw new Error(`${operation} 실패: ${error.message}`);
}
