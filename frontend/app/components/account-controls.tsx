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
      <Link href="/survey" className="whitespace-nowrap text-xs font-medium text-body hover:text-ink hover:no-underline">
        설정
      </Link>
      <SignOutButton />
    </div>
  );
}
