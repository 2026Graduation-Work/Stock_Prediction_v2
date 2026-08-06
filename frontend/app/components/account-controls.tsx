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
  const avatarLabel = Array.from(displayName)[0] ?? profile.avatarLabel;

  return (
    <div className="ml-auto flex flex-none items-center gap-1.5 sm:gap-2.5">
      <div className="hidden h-[34px] items-center gap-2 rounded-[8px] border border-line bg-field pl-2 pr-3 lg:flex">
        <div className="grid size-[22px] place-items-center rounded-full bg-brand-soft text-[11px] font-bold text-brand">
          {avatarLabel}
        </div>
        <span className="whitespace-nowrap text-[12px] font-semibold">
          {displayName}
          <span className="hidden xl:inline"> · {profile.profileTypeLabel}</span>
        </span>
      </div>
      <Link
        href="/survey"
        className="inline-flex h-[34px] items-center whitespace-nowrap rounded-[8px] border border-edge bg-white px-3.5 text-[13px] font-semibold text-body hover:border-ghost hover:bg-field hover:no-underline"
      >
        설정
      </Link>
      <SignOutButton />
    </div>
  );
}
