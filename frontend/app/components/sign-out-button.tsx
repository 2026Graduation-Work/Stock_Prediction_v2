"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useOnboarding } from "./onboarding-provider";

export default function SignOutButton() {
  const router = useRouter();
  const { logOut } = useOnboarding();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSignOut() {
    setSubmitting(true);
    setError("");
    try {
      await logOut();
      router.replace("/login");
    } catch (signOutError) {
      setError(
        signOutError instanceof Error
          ? signOutError.message
          : "로그아웃하지 못했습니다.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex items-center">
      <button
        type="button"
        onClick={() => void handleSignOut()}
        disabled={submitting}
        title={error || undefined}
        className="inline-flex h-[34px] items-center whitespace-nowrap rounded-[8px] border border-edge bg-white px-2.5 text-[12px] font-semibold text-muted hover:border-ghost hover:bg-field hover:text-ink disabled:cursor-not-allowed disabled:opacity-50 sm:px-3"
      >
        {submitting ? (
          "처리 중"
        ) : (
          <>
            <span className="sm:hidden">나가기</span>
            <span className="hidden sm:inline">로그아웃</span>
          </>
        )}
      </button>
      {error && (
        <span role="alert" className="sr-only">
          {error}
        </span>
      )}
    </div>
  );
}
