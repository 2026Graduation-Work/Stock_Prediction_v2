import Link from "next/link";
import AccountControls from "./account-controls";
import MarketStatusBar from "./market-status-bar";
import type { InvestorProfileSummary, MarketStatus } from "@/lib/types";

interface SiteHeaderProps {
  profile: InvestorProfileSummary;
  marketStatus: MarketStatus;
  query?: string;
  onQueryChange?: (value: string) => void;
  activePage?: "dashboard" | "performance";
  sectionLabel?: string;
}

const NAV_ITEMS = [
  { href: "/", label: "대시보드", page: "dashboard" },
  { href: "/performance", label: "모델 성능", page: "performance" },
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
    <header className="sticky top-0 z-50 border-b border-line bg-white shadow-[0_1px_2px_rgba(16,24,40,0.03)]">
      <div className="mx-auto box-border flex min-h-[60px] w-full max-w-[1440px] flex-wrap items-center gap-2 px-4 py-2 sm:h-[60px] sm:flex-nowrap sm:gap-4 sm:px-6 sm:py-0 lg:px-8">
        <Link
          href="/"
          className="flex flex-none items-center gap-2.5 text-ink hover:no-underline"
        >
          <div className="grid size-7 place-items-center rounded-lg bg-brand text-sm font-extrabold text-white">
            S
          </div>
          <div className="hidden text-[17px] font-extrabold sm:block">시그널랩</div>
        </Link>

        <nav aria-label="주요 화면" className="flex flex-none items-center rounded-lg bg-field p-1">
          {NAV_ITEMS.map((item) => {
            const active = item.page === activePage;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`inline-flex h-7 items-center rounded-md px-2.5 text-[12px] font-bold hover:no-underline ${
                  active
                    ? "bg-white text-brand shadow-[0_1px_2px_rgba(16,24,40,0.08)]"
                    : "text-muted hover:bg-white hover:text-ink"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        {hasSearch ? (
          <div className="order-last flex min-w-0 basis-full items-center sm:order-none sm:flex-1 sm:basis-auto">
            <input
              value={query ?? ""}
              onChange={(event) => onQueryChange?.(event.target.value)}
              placeholder="종목명 또는 코드 검색"
              className="box-border h-9 w-full min-w-0 max-w-none rounded-[8px] border border-edge bg-field px-3.5 text-[13px] text-ink outline-none placeholder:text-faint focus:border-brand focus:bg-white sm:min-w-[170px] sm:max-w-[260px]"
            />
          </div>
        ) : (
          <div className="hidden min-w-0 flex-1 truncate text-[13px] font-semibold text-muted sm:block">
            {sectionLabel}
          </div>
        )}

        <AccountControls profile={profile} />
      </div>
      <MarketStatusBar status={marketStatus} />
    </header>
  );
}
