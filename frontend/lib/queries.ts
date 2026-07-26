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
  maxRiskTier: number;
  avoidedLabels: string[];
  excludedStocks: ExcludedStock[];
}

export interface DashboardData {
  marketStatus: MarketStatus;
  stocks: RecommendedStock[];
  holdingAlerts: RecommendedStock[];
  holdings: PortfolioHolding[];
  profile: InvestorProfileSummary;
  maxRiskTier: number;
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

interface ProfileQueryContext {
  settings: ProfileSettings;
  result: ProfileQueryResult;
}

const PREDICTION_COLUMNS =
  "stock_code,prediction_date,signal_light,rank_percentile,return_low,return_high,return_ci_level,bucket_hit_rate,similar_case_count,horizon_h5,horizon_h10,horizon_h20,horizon_agreement,caution,display_order" as const;

const STOCK_COLUMNS = "code,name,market,risk_grade,risk_flags";

export async function getDashboardData(
  userId = DEMO_USER_ID,
): Promise<DashboardData> {
  const [currentMarketStatus, stocks, currentHoldingAlerts, holdings, profileResult] =
    await Promise.all([
      getMarketStatus(),
      getRecommendedStocks(userId),
      getHoldingAlerts(userId),
      getPortfolio(userId),
      getProfile(userId),
    ]);

  return {
    marketStatus: currentMarketStatus,
    stocks,
    holdingAlerts: currentHoldingAlerts,
    holdings,
    profile: profileResult.profile,
    maxRiskTier: profileResult.maxRiskTier,
    avoidedLabels: profileResult.avoidedLabels,
    excludedStocks: profileResult.excludedStocks,
  };
}

export async function getAuthenticatedDashboardData(): Promise<DashboardData> {
  const client = getSupabaseClient();
  if (!client) throw new Error("Supabase 환경변수가 설정되지 않았습니다.");

  const { data: authData, error: authError } = await client.auth.getUser();
  assertQuery(authError, "로그인 사용자 확인");
  if (!authData.user) throw new Error("로그인 사용자 정보가 없습니다.");

  const { data: appUser, error: appUserError } = await client
    .from("users")
    .select("id")
    .eq("auth_user_id", authData.user.id)
    .maybeSingle();
  assertQuery(appUserError, "대시보드 사용자 확인");
  if (!appUser) throw new Error("연결된 서비스 사용자 정보가 없습니다.");

  const [currentMarketStatus, profileContext, holdingRows] = await Promise.all([
    queryMarketStatus(client),
    loadProfileQueryContext(client, appUser.id),
    loadHoldings(client, appUser.id),
  ]);
  const [stocks, currentHoldingAlerts, holdings] = await Promise.all([
    queryRecommendedStocks(client, appUser.id, profileContext.settings),
    queryHoldingAlerts(client, appUser.id, profileContext.settings, holdingRows),
    queryPortfolio(client, appUser.id, profileContext.settings, holdingRows),
  ]);

  return {
    marketStatus: currentMarketStatus,
    stocks,
    holdingAlerts: currentHoldingAlerts,
    holdings,
    profile: profileContext.result.profile,
    maxRiskTier: profileContext.result.maxRiskTier,
    avoidedLabels: profileContext.result.avoidedLabels,
    excludedStocks: profileContext.result.excludedStocks,
  };
}

export async function getMarketStatus(): Promise<MarketStatus> {
  return withFallback("market status", marketStatus, queryMarketStatus);
}

export async function getRecommendedStocks(
  userId = DEMO_USER_ID,
): Promise<RecommendedStock[]> {
  return withFallback("recommended stocks", recommendedStocks, (client) =>
    queryRecommendedStocks(client, userId),
  );
}

export async function getHoldingAlerts(
  userId = DEMO_USER_ID,
): Promise<RecommendedStock[]> {
  return withFallback("holding alerts", holdingAlerts, (client) =>
    queryHoldingAlerts(client, userId),
  );
}

export async function getPortfolio(
  userId = DEMO_USER_ID,
): Promise<PortfolioHolding[]> {
  return withFallback("portfolio", portfolioHoldings, (client) =>
    queryPortfolio(client, userId),
  );
}

export async function getProfile(
  userId = DEMO_USER_ID,
): Promise<ProfileQueryResult> {
  const fallback: ProfileQueryResult = {
    profile: investorProfile,
    maxRiskTier: 4,
    avoidedLabels: avoidanceNotice.avoidedLabels,
    excludedStocks: avoidanceNotice.excludedStocks,
  };

  return withFallback("profile", fallback, (client) => queryProfile(client, userId));
}

async function queryMarketStatus(client: SupabaseClient): Promise<MarketStatus> {
  const { data, error } = await client
    .from("market_status")
    .select("status_date,condition,volatility_score,volume_score,index_quotes")
    .order("status_date", { ascending: false })
    .limit(1)
    .maybeSingle();
  assertQuery(error, "시장 상태 조회");
  if (!data) throw new Error("시장 상태 데이터가 없습니다.");
  return mapMarketStatus(data as MarketStatusRow);
}

async function queryRecommendedStocks(
  client: SupabaseClient,
  userId: string,
  profileSettings?: ProfileSettings,
): Promise<RecommendedStock[]> {
  const settings = profileSettings ?? (await loadProfileSettings(client, userId));
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
}

async function queryHoldingAlerts(
  client: SupabaseClient,
  userId: string,
  profileSettings?: ProfileSettings,
  portfolioRows?: PortfolioHoldingRow[],
): Promise<RecommendedStock[]> {
  const [settings, holdings] = await Promise.all([
    profileSettings ?? loadProfileSettings(client, userId),
    portfolioRows ?? loadHoldings(client, userId),
  ]);
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
}

async function queryPortfolio(
  client: SupabaseClient,
  userId: string,
  profileSettings?: ProfileSettings,
  portfolioRows?: PortfolioHoldingRow[],
): Promise<PortfolioHolding[]> {
  const [settings, holdings] = await Promise.all([
    profileSettings ?? loadProfileSettings(client, userId),
    portfolioRows ?? loadHoldings(client, userId),
  ]);
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
}

async function queryProfile(
  client: SupabaseClient,
  userId: string,
): Promise<ProfileQueryResult> {
  return (await loadProfileQueryContext(client, userId)).result;
}

async function loadProfileQueryContext(
  client: SupabaseClient,
  userId: string,
): Promise<ProfileQueryContext> {
  const [userResult, profileResult, avoidedResult] = await Promise.all([
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
  ]);
  assertQuery(userResult.error, "사용자 조회");
  assertQuery(profileResult.error, "IPS 프로필 조회");
  assertQuery(avoidedResult.error, "회피 설정 조회");
  if (!userResult.data || !profileResult.data) {
    throw new Error("사용자 또는 IPS 프로필 데이터가 없습니다.");
  }

  const avoidedRows = (avoidedResult.data ?? []) as AvoidedAssetRow[];
  const profile = profileResult.data as IpsProfileRow;
  const stocks = await loadAvoidedStocks(client, avoidedRows);
  return {
    settings: toProfileSettings(profile, avoidedRows),
    result: {
      profile: mapProfileSummary(userResult.data as UserRow, profile),
      maxRiskTier: profile.max_risk_tier,
      avoidedLabels: mapAvoidedAssetLabels(avoidedRows),
      excludedStocks: mapExcludedStocks(stocks, avoidedRows),
    },
  };
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

  return toProfileSettings(
    profileResult.data as ProfileSettingsRow,
    (avoidedResult.data ?? []) as AvoidedAssetRow[],
  );
}

function toProfileSettings(
  profile: ProfileSettingsRow,
  avoidedRows: AvoidedAssetRow[],
): ProfileSettings {
  return {
    profileType: profile.profile_type,
    maxRiskTier: profile.max_risk_tier,
    avoided: new Set(avoidedRows.map(({ asset_type }) => asset_type)),
  };
}

async function loadAvoidedStocks(
  client: SupabaseClient,
  avoidedRows: AvoidedAssetRow[],
): Promise<StockRow[]> {
  const avoidedTypes = avoidedRows.map(({ asset_type }) => asset_type);
  if (!avoidedTypes.length) return [];

  const { data, error } = await client
    .from("stocks")
    .select(STOCK_COLUMNS)
    .eq("is_active", true)
    .overlaps("risk_flags", avoidedTypes);
  assertQuery(error, "회피 대상 종목 조회");
  return (data ?? []) as StockRow[];
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
    .select("stock_code,quantity,avg_buy_price,display_order")
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
