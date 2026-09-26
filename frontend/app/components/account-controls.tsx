"use client";

import Link from "next/link";
import type { InvestorProfileSummary } from "@/lib/types";
import { useOnboarding } from "./onboarding-provider";
import SignOutButton from "./sign-out-button";

export default function AccountControls({
  profile,
}: {
  profile: InvestorProfileSummary;
}) {
  const { state } = useOnboarding();
  const displayName = state.displayName?.trim() || profile.displayName;

  return (
    <div className="ml-auto flex flex-none items-center gap-3">
      <span className="hidden whitespace-nowrap text-xs text-muted lg:inline">
        {displayName} · {profile.profileTypeLabel}
      </span>
      <details className="group relative">
        <summary className="cursor-pointer list-none whitespace-nowrap text-xs font-medium text-body hover:text-ink">
          계정
        </summary>
        <div className="absolute right-0 top-7 z-50 flex w-44 flex-col overflow-hidden rounded-md glass py-1">
          <Link href="/survey" className="px-4 py-2.5 text-sm text-ink hover:bg-field hover:text-ink hover:no-underline">
            내 성향 다시 진단
          </Link>
          <Link href="/portfolio" className="px-4 py-2.5 text-sm text-ink hover:bg-field hover:text-ink hover:no-underline">
            보유 종목 편집
          </Link>
        </div>
      </details>
      <SignOutButton />
    </div>
  );
}
