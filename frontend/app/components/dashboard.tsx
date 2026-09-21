"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import DisclaimerFooter from "./disclaimer-footer";
import InvestorProfileCard from "./investor-profile-card";
import { useOnboarding } from "./onboarding-provider";
import PortfolioHeatmap from "./portfolio-heatmap";
import SiteHeader from "./site-header";
import StockCard from "./stock-card";
import {
  getAuthenticatedDashboardData,
  type DashboardData,
} from "@/lib/queries";
import type { RecommendedStock } from "@/lib/types";
import { AVOIDED_ASSET_LABELS, summaryFromProfilingOutput } from "@/lib/profiling-rules";
import { holdingAlertsOutside } from "@/lib/recommendation-filter";
import {
  getSavedProfileSnapshot,
  getServerProfileSnapshot,
  parseSavedProfile,
  subscribeToSavedProfile,
} from "@/lib/save-profile";

function SectionTitle({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="flex items-baseline gap-2.5 px-0.5">
      <h2 className="text-xl font-semibold">{title}</h2>
      <span className="text-xs text-faint">{subtitle}</span>
    </div>
  );
}

interface AuthenticatedDashboardResult {
  userId: string;
  data?: DashboardData;
  error?: string;
}

export default function Dashboard(initialData: DashboardData) {
  const { state: onboardingState } = useOnboarding();
  const [query, setQuery] = useState("");
  const [showExcluded, setShowExcluded] = useState(false);
  const [authenticatedResult, setAuthenticatedResult] =
    useState<AuthenticatedDashboardResult | null>(null);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    const userId = onboardingState.userId;
    if (onboardingState.mode !== "supabase" || !userId) return;

    let active = true;
    getAuthenticatedDashboardData()
      .then((data) => {
        if (!active) return;
        setAuthenticatedResult({ userId, data });
      })
      .catch((error: unknown) => {
        if (!active) return;
        setAuthenticatedResult({
          userId,
          error:
            error instanceof Error
              ? error.message
              : "내 대시보드 데이터를 불러오지 못했습니다.",
        });
      });

    return () => {
      active = false;
    };
  }, [onboardingState.mode, onboardingState.userId, requestVersion]);

  const currentAuthenticatedResult =
    authenticatedResult?.userId === onboardingState.userId
      ? authenticatedResult
      : null;
  const authenticatedData = currentAuthenticatedResult?.data ?? null;
  const dataError = currentAuthenticatedResult?.error ?? "";
  const currentData = authenticatedData ?? initialData;
  const {
    marketStatus,
    profile,
    maxRiskTier,
    stocks = [],
    holdingAlerts: rawHoldingAlerts = [],
    holdings = [],
    excludedStocks = [],
    avoidedLabels = [],
  } = currentData;
  const holdingAlerts = holdingAlertsOutside(rawHoldingAlerts, stocks);
  const loadingAuthenticatedData =
    onboardingState.mode === "supabase" && !authenticatedData && !dataError;
  const savedSnapshot = useSyncExternalStore(
    subscribeToSavedProfile,
    getSavedProfileSnapshot,
    getServerProfileSnapshot,
  );
  const savedProfile = parseSavedProfile(savedSnapshot);
  const activeProfile = savedProfile
    ? summaryFromProfilingOutput(savedProfile, profile)
    : profile;
  const activeAvoidedLabels = savedProfile
    ? savedProfile.constraints.avoided_assets
        .map((asset) => AVOIDED_ASSET_LABELS[asset])
        .filter((label): label is string => Boolean(label))
    : avoidedLabels;
  const activeExcludedStocks = activeAvoidedLabels.length > 0 ? excludedStocks : [];
  const keyword = query.trim();
  const normalized = keyword.toLowerCase();
  const matches = (stock: RecommendedStock) =>
    stock.name.toLowerCase().includes(normalized) ||
    stock.code.toLowerCase().includes(normalized);
  const visibleStocks = keyword ? stocks.filter(matches) : stocks;
  const visibleAlerts = keyword ? holdingAlerts.filter(matches) : holdingAlerts;
  const noResult = keyword && visibleStocks.length === 0 && visibleAlerts.length === 0;
  const safeMaxRiskTier =
    Number.isInteger(maxRiskTier) && maxRiskTier >= 1 && maxRiskTier <= 5
      ? maxRiskTier
      : 4;
  const riskTierLabel =
    safeMaxRiskTier === 5 ? "5등급" : `${safeMaxRiskTier}~5등급`;

  function retryAuthenticatedData() {
    setAuthenticatedResult(null);
    setRequestVersion((version) => version + 1);
  }

  return (
    <div className="w-full">
      <SiteHeader
        query={query}
        onQueryChange={setQuery}
        profile={activeProfile}
        marketStatus={marketStatus}
      />

      <div
        className="mx-auto box-border flex w-full max-w-[1440px] flex-col gap-6 px-5 pt-6 sm:px-8"
        aria-busy={loadingAuthenticatedData}
      >
        {dataError && (
          <div
            role="alert"
            className="flex flex-col gap-3 rounded-lg border border-warn-line bg-warn-tint px-4 py-3 sm:flex-row sm:items-center"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium text-warn">
                내 데이터를 불러오지 못해 샘플 데이터를 표시합니다.
              </p>
              <p className="mt-1 break-words text-xs text-warn">{dataError}</p>
            </div>
            <button
              type="button"
              onClick={retryAuthenticatedData}
              className="h-9 flex-none rounded-lg border border-warn-line bg-white px-4 text-xs font-medium text-warn hover:bg-warn-tint sm:ml-auto"
            >
              다시 시도
            </button>
          </div>
        )}

        {loadingAuthenticatedData ? (
          <DashboardLoading />
        ) : (
          <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[1fr_356px]">
            <main className="flex flex-col gap-4">
              <SectionTitle
                title="오늘의 추천 종목"
                subtitle={`${activeProfile.profileTypeLabel} 기준 · 성향에 맞는 위험등급 ${riskTierLabel}`}
              />

              {!keyword && activeExcludedStocks.length > 0 && (
                <div className="flex flex-col gap-2 rounded-md bg-field px-4 py-3">
                  <div className="flex items-center gap-2.5">
                    <span className="text-sm text-body">
                      회피 설정({activeAvoidedLabels.join("·")})으로{" "}
                      {activeExcludedStocks.length}개 종목이 제외되었습니다
                    </span>
                    <button
                      type="button"
                      onClick={() => setShowExcluded((open) => !open)}
                      className="ml-auto text-xs font-medium text-brand hover:text-brand-deep hover:underline"
                    >
                      {showExcluded ? "접기" : "제외 종목 보기"}
                    </button>
                  </div>
                  {showExcluded && (
                    <ul className="flex flex-col gap-1 border-t border-line pt-2">
                      {activeExcludedStocks.map((stock) => (
                        <li key={stock.code} className="text-xs text-body">
                          {stock.name}{" "}
                          <span className="text-faint">
                            ({stock.code}) · 제외 사유: {stock.reason}
                          </span>
                        </li>
                      ))}
                      <li className="text-xs text-faint">
                        회피 항목은 설정에서 변경할 수 있습니다
                      </li>
                    </ul>
                  )}
                </div>
              )}

              {!keyword && stocks.length === 0 && holdingAlerts.length === 0 && (
                <div className="rounded-lg border border-dashed border-edge bg-white p-8 text-center">
                  <p className="text-sm font-medium text-ink">오늘 보여 줄 종목 신호가 아직 없어요</p>
                  <p className="mt-1.5 text-sm text-muted">
                    예측 데이터가 적재되면 여기에 나타나요. 종목명이나 코드로 검색하면 종목 정보는 바로 볼 수
                    있어요.
                  </p>
                </div>
              )}

              {visibleStocks.map((stock) => (
                <StockCard key={stock.code} stock={stock} />
              ))}

              {visibleAlerts.length > 0 && (
                <>
                  <div className="pt-2">
                    <SectionTitle
                      title="보유 종목 알림"
                      subtitle="추천 아님 · 보유 중인 종목의 오늘 신호"
                    />
                  </div>
                  {visibleAlerts.map((stock) => (
                    <StockCard key={stock.code} stock={stock} variant="holding" />
                  ))}
                </>
              )}

              {noResult && (
                <div className="flex flex-col gap-2 rounded-lg border border-dashed border-edge bg-white p-8 text-center">
                  <span className="text-sm font-medium">
                    &lsquo;{keyword}&rsquo; — 오늘의 추천 목록에 없는 종목입니다
                  </span>
                  <span className="text-sm text-muted">
                    추천 밖 종목도 조회할 수 있습니다.{" "}
                    <Link href={`/stocks/${encodeURIComponent(keyword)}`}>
                      종목 조회로 이동 →
                    </Link>
                  </span>
                </div>
              )}
            </main>

            <aside className="flex flex-col gap-4">
              <InvestorProfileCard
                profile={activeProfile}
                avoidedLabels={activeAvoidedLabels}
              />
              <PortfolioHeatmap holdings={holdings} />
            </aside>
          </div>
        )}
      </div>

      <DisclaimerFooter fixed={false} />
    </div>
  );
}

function DashboardLoading() {
  return (
    <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[1fr_356px]">
      <main className="flex flex-col gap-3.5" aria-label="내 대시보드 불러오는 중">
        <div className="h-6 w-44 animate-pulse rounded bg-track" />
        {[0, 1, 2].map((item) => (
          <div
            key={item}
            className="h-[190px] animate-pulse rounded-lg border border-line bg-white p-6"
          >
            <div className="h-5 w-36 rounded bg-track" />
            <div className="mt-8 h-3 w-full rounded bg-field" />
            <div className="mt-3 h-3 w-3/4 rounded bg-field" />
          </div>
        ))}
      </main>
      <aside className="flex flex-col gap-4">
        <div className="h-[280px] animate-pulse rounded-lg border border-line bg-white p-5">
          <div className="h-5 w-28 rounded bg-track" />
          <div className="mt-8 h-3 w-full rounded bg-field" />
          <div className="mt-4 h-3 w-4/5 rounded bg-field" />
        </div>
        <div className="h-[320px] animate-pulse rounded-lg border border-line bg-white p-5">
          <div className="h-5 w-32 rounded bg-track" />
        </div>
      </aside>
    </div>
  );
}
