import Link from "next/link";
import type { InvestorProfileSummary } from "@/lib/types";

interface SiteHeaderProps {
  query: string;
  onQueryChange: (value: string) => void;
  profile: InvestorProfileSummary;
}

export default function SiteHeader({ query, onQueryChange, profile }: SiteHeaderProps) {
  return (
    <header className="sticky top-0 z-50 border-b border-line bg-white">
      <div className="mx-auto box-border flex h-16 w-[1440px] items-center gap-6 px-8">
        <Link href="/" className="flex items-center gap-2.5 text-ink hover:no-underline">
          <div className="grid size-7 place-items-center rounded-lg bg-brand text-sm font-extrabold text-white">
            S
          </div>
          <div className="text-[17px] font-extrabold tracking-tight">시그널랩</div>
        </Link>
        <div className="flex max-w-[640px] flex-1 items-center gap-3">
          <input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="종목명 또는 코드 검색"
            className="box-border h-[38px] w-[380px] flex-none rounded-[10px] border border-edge bg-field px-3.5 text-sm text-ink outline-none placeholder:text-faint focus:border-brand focus:bg-white"
          />
          <span className="whitespace-nowrap text-xs text-faint">
            추천 목록 밖 종목도 조회할 수 있어요
          </span>
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-2.5">
          <div className="flex h-[34px] items-center gap-2 rounded-full border border-line bg-field pl-2 pr-3.5">
            <div className="grid size-[22px] place-items-center rounded-full bg-brand-soft text-[11px] font-bold text-brand">
              {profile.avatarLabel}
            </div>
            <span className="text-[13px] font-semibold">
              {profile.displayName} · {profile.profileTypeLabel}
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
    </header>
  );
}
