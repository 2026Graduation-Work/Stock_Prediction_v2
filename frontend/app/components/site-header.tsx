import Link from "next/link";
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
      <div className="mx-auto box-border flex h-[60px] w-full max-w-[1440px] items-center gap-4 px-6 lg:px-8">
        <Link
          href="/"
          className="flex flex-none items-center gap-2.5 text-ink hover:no-underline"
        >
          <div className="grid size-7 place-items-center rounded-lg bg-brand text-sm font-extrabold text-white">
            S
          </div>
          <div className="text-[17px] font-extrabold tracking-tight">시그널랩</div>
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
          <div className="flex min-w-0 flex-1 items-center">
            <input
              value={query ?? ""}
              onChange={(event) => onQueryChange?.(event.target.value)}
              placeholder="종목명 또는 코드 검색"
              className="box-border h-9 w-full min-w-[170px] max-w-[260px] rounded-[8px] border border-edge bg-field px-3.5 text-[13px] text-ink outline-none placeholder:text-faint focus:border-brand focus:bg-white"
            />
          </div>
        ) : (
          <div className="min-w-0 flex-1 truncate text-[13px] font-semibold text-muted">
            {sectionLabel}
          </div>
        )}

        <div className="flex flex-none items-center gap-2.5">
          <div className="flex h-[34px] items-center gap-2 rounded-[8px] border border-line bg-field pl-2 pr-3">
            <div className="grid size-[22px] place-items-center rounded-full bg-brand-soft text-[11px] font-bold text-brand">
              {profile.avatarLabel}
            </div>
            <span className="whitespace-nowrap text-[12px] font-semibold">
              {profile.displayName}
              <span className="hidden xl:inline"> · {profile.profileTypeLabel}</span>
            </span>
          </div>
          <button
            type="button"
            className="h-[34px] whitespace-nowrap rounded-[10px] border border-edge bg-white px-3.5 text-[13px] font-semibold text-body hover:border-ghost hover:bg-field"
          >
            설정
          </button>
        </div>
      </div>
      <MarketStatusBar status={marketStatus} />
    </header>
  );
}
