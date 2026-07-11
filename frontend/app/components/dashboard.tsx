"use client";

import { useState } from "react";
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
  RecommendedStock,
} from "@/lib/types";

interface DashboardProps {
  marketStatus: MarketStatus;
  profile: InvestorProfileSummary;
  stocks: RecommendedStock[];
  holdings: PortfolioHolding[];
  excludedCount: number;
  avoidedLabels: string[];
}

export default function Dashboard({
  marketStatus,
  profile,
  stocks,
  holdings,
  excludedCount,
  avoidedLabels,
}: DashboardProps) {
  const [query, setQuery] = useState("");
  const keyword = query.trim();
  const visibleStocks = keyword
    ? stocks.filter((stock) => stock.name.includes(keyword) || stock.code.includes(keyword))
    : stocks;

  return (
    <div className="min-w-[1440px] pb-[72px]">
      <SiteHeader query={query} onQueryChange={setQuery} profile={profile} />

      <div className="mx-auto box-border flex w-[1440px] flex-col gap-5 px-8 pt-5">
        <MarketStatusBar status={marketStatus} />

        <div className="grid grid-cols-[1fr_356px] items-start gap-5">
          <main className="flex flex-col gap-3.5">
            <div className="flex items-baseline gap-2.5 px-0.5">
              <h2 className="text-lg font-extrabold tracking-tight">오늘의 추천 종목</h2>
              <span className="text-[12.5px] text-faint">
                {profile.profileTypeLabel} 기준 · 위험 4·5등급 위주 선별
              </span>
            </div>

            {!keyword && excludedCount > 0 && (
              <div className="flex items-center gap-2.5 rounded-[10px] border border-line bg-track px-4 py-2.5">
                <span className="grid size-4 flex-none place-items-center rounded-full bg-faint text-[10px] font-extrabold text-white">
                  i
                </span>
                <span className="text-[13px] text-body">
                  회피 설정({avoidedLabels.join("·")})으로 {excludedCount}개 종목이
                  제외되었습니다
                </span>
                <button type="button" className="ml-auto text-[12.5px] font-medium text-brand hover:text-brand-deep hover:underline">
                  회피 설정 변경
                </button>
              </div>
            )}

            {visibleStocks.map((stock) => (
              <StockCard key={stock.code} stock={stock} />
            ))}

            {keyword && visibleStocks.length === 0 && (
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
            <InvestorProfileCard profile={profile} />
            <PortfolioHeatmap holdings={holdings} />
          </aside>
        </div>
      </div>

      <DisclaimerFooter />
    </div>
  );
}
