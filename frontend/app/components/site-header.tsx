import Link from "next/link";
import AccountControls from "./account-controls";
import MarketStatusBar from "./market-status-bar";
import type { InvestorProfileSummary, MarketStatus } from "@/lib/types";
import { SERVICE_NAME } from "@/lib/brand";

interface SiteHeaderProps {
  profile: InvestorProfileSummary;
  marketStatus: MarketStatus;
  query?: string;
  onQueryChange?: (value: string) => void;
  activePage?: "dashboard" | "performance" | "portfolio";
  sectionLabel?: string;
}

const NAV_ITEMS = [
  { href: "/", label: "대시보드", page: "dashboard" },
  { href: "/portfolio", label: "보유 종목", page: "portfolio" },
  { href: "/performance", label: "모델 성적표", page: "performance" },
] as const;

export default function SiteHeader({
  query,
  onQueryChange,
  profile,
  marketStatus,
  activePage = "dashboard",
  sectionLabel,
}: SiteHeaderProps) {
  const hasSearch = onQueryChange !== undefined;

  return (
    <header className="sticky top-0 z-50 border-b border-line/70 bg-white/80 backdrop-blur-xl backdrop-saturate-150">
      <div className="mx-auto box-border flex min-h-14 w-full max-w-[1200px] flex-wrap items-center gap-x-5 gap-y-2 px-4 py-2 sm:h-14 sm:flex-nowrap sm:px-6 sm:py-0 lg:px-8">
        <Link href="/" className="flex-none text-lg font-semibold text-brand hover:text-brand hover:no-underline">
          {SERVICE_NAME}
        </Link>

        <nav aria-label="주요 화면" className="flex flex-none items-center gap-4 self-stretch">
          {NAV_ITEMS.map((item) => {
            const active = item.page === activePage;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`relative inline-flex h-full items-center text-xs font-medium hover:no-underline ${
                  active ? "text-ink" : "text-muted hover:text-ink"
                }`}
              >
                {item.label}
                {active && (
                  <span className="absolute inset-x-0 bottom-0 h-0.5 rounded-full bg-brand-accent" aria-hidden />
                )}
              </Link>
            );
          })}
        </nav>

        {hasSearch ? (
          <div className="order-last flex min-w-0 basis-full items-center sm:order-none sm:flex-1 sm:basis-auto sm:justify-end">
            <input
              type="search"
              value={query ?? ""}
              onChange={(event) => onQueryChange?.(event.target.value)}
              placeholder="종목명 또는 코드 검색"
              aria-label="종목 검색"
              className="box-border h-9 w-full min-w-0 rounded-md bg-track px-3.5 text-sm text-ink outline-none focus:bg-white focus:ring-2 focus:ring-brand/30 sm:max-w-[280px]"
            />
          </div>
        ) : (
          <div className="hidden min-w-0 flex-1 truncate text-sm font-medium text-muted sm:block">
            {sectionLabel}
          </div>
        )}

        <AccountControls profile={profile} />
      </div>
      <MarketStatusBar status={marketStatus} />
    </header>
  );
}
