"use client";

import { useState, useSyncExternalStore } from "react";
import Link from "next/link";
import DisclaimerFooter from "./disclaimer-footer";
import InvestorProfileCard from "./investor-profile-card";
import MarketStatusBar from "./market-status-bar";
import PortfolioHeatmap from "./portfolio-heatmap";
import SiteHeader from "./site-header";
import StockCard from "./stock-card";
import type {
  InvestorProfileSummary,
  MarketStatus,
  PortfolioHolding,
  ProfilingOutput,
  RecommendedStock,
} from "@/lib/types";
import { AVOIDED_ASSET_LABELS } from "@/lib/profiling-rules";
import {
  getSavedProfileSnapshot,
  getServerProfileSnapshot,
  parseSavedProfile,
  subscribeToSavedProfile,
} from "@/lib/save-profile";

interface ExcludedStock {
  name: string;
  code: string;
  reason: string;
}

interface DashboardProps {
  marketStatus: MarketStatus;
  profile: InvestorProfileSummary;
  stocks: RecommendedStock[];
  holdingAlerts: RecommendedStock[];
  holdings: PortfolioHolding[];
  excludedStocks: ExcludedStock[];
  avoidedLabels: string[];
}

function SectionTitle({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="flex items-baseline gap-2.5 px-0.5">
      <h2 className="text-lg font-extrabold tracking-tight">{title}</h2>
      <span className="text-[12.5px] text-faint">{subtitle}</span>
    </div>
  );
}

function profileSummaryFromOutput(
  output: ProfilingOutput,
  fallback: InvestorProfileSummary,
): InvestorProfileSummary {
  const months = output.investor_profile.time_horizon_months;
  const horizon = months <= 24 ? "short" : months <= 60 ? "mid" : "long";
  const stable = output.investor_profile.profile_type === "stable";
  const completedAt = new Date(output.timestamp);
  const surveyedAt = Number.isNaN(completedAt.getTime())
    ? fallback.surveyedAt
    : `${completedAt.getFullYear()}.${String(completedAt.getMonth() + 1).padStart(2, "0")}`;
  return {
    ...fallback,
    profileTypeLabel: stable ? "안정추구형" : "수익추구형",
    personaLabel: stable ? "신중한 중장기 투자자" : "적극적인 기회 탐색형 투자자",
    riskTolerance: Math.round(output.investor_profile.risk_tolerance * 100),
    sentimentSensitivity: Math.round(output.psychological_state.fomo_index * 100),
    horizon,
    surveyedAt,
  };
}

export default function Dashboard({
  marketStatus,
  profile,
  stocks,
  holdingAlerts,
  holdings,
  excludedStocks,
  avoidedLabels,
}: DashboardProps) {
  const [query, setQuery] = useState("");
  const [showExcluded, setShowExcluded] = useState(false);
  const savedSnapshot = useSyncExternalStore(
    subscribeToSavedProfile,
    getSavedProfileSnapshot,
    getServerProfileSnapshot,
  );
  const savedProfile = parseSavedProfile(savedSnapshot);
  const activeProfile = savedProfile
    ? profileSummaryFromOutput(savedProfile, profile)
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

  return (
    <div className="w-full pb-[72px]">
      <SiteHeader query={query} onQueryChange={setQuery} profile={activeProfile} />

      <div className="mx-auto box-border flex w-full max-w-[1440px] flex-col gap-5 px-8 pt-5">
        <MarketStatusBar status={marketStatus} />

        <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[1fr_356px]">
          <main className="flex flex-col gap-3.5">
            <SectionTitle
              title="오늘의 추천 종목"
              subtitle={`${activeProfile.profileTypeLabel} 기준 · 위험 4·5등급 위주 선별`}
            />

            {!keyword && activeExcludedStocks.length > 0 && (
              <div className="flex flex-col gap-2 rounded-[10px] border border-line bg-track px-4 py-2.5">
                <div className="flex items-center gap-2.5">
                  <span className="grid size-4 flex-none place-items-center rounded-full bg-faint text-[10px] font-extrabold text-white">
                    i
                  </span>
                  <span className="text-[13px] text-body">
                    회피 설정({activeAvoidedLabels.join("·")})으로 {activeExcludedStocks.length}개
                    종목이 제외되었습니다
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowExcluded((open) => !open)}
                    className="ml-auto text-[12.5px] font-medium text-brand hover:text-brand-deep hover:underline"
                  >
                    {showExcluded ? "접기" : "제외 종목 보기"}
                  </button>
                </div>
                {showExcluded && (
                  <ul className="flex flex-col gap-1 border-t border-line pl-[26px] pt-2">
                    {activeExcludedStocks.map((stock) => (
                      <li key={stock.code} className="text-[12.5px] text-body">
                        {stock.name}{" "}
                        <span className="text-faint">
                          ({stock.code}) · 제외 사유: {stock.reason}
                        </span>
                      </li>
                    ))}
                    <li className="text-[11.5px] text-faint">
                      회피 항목은 설정에서 변경할 수 있습니다
                    </li>
                  </ul>
                )}
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
                  <StockCard key={stock.code} stock={stock} />
                ))}
              </>
            )}

            {noResult && (
              <div className="flex flex-col gap-2 rounded-[14px] border border-dashed border-edge bg-white p-8 text-center">
                <span className="text-sm font-bold">
                  &lsquo;{keyword}&rsquo; — 오늘의 추천 목록에 없는 종목입니다
                </span>
                <span className="text-[13px] text-muted">
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
      </div>

      <DisclaimerFooter />
    </div>
  );
}
