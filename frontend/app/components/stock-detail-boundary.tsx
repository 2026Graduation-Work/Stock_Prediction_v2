"use client";

import { useEffect, useState } from "react";
import StockDetailView from "./stock-detail";
import { useOnboarding } from "./onboarding-provider";
import {
  getAuthenticatedStockDetailData,
  type StockDetailData,
} from "@/lib/queries";

interface AuthenticatedDetailResult {
  userId: string;
  code: string;
  data?: StockDetailData;
  error?: string;
}

export default function StockDetailBoundary({
  code,
  initialData,
}: {
  code: string;
  initialData: StockDetailData;
}) {
  const { state: onboardingState } = useOnboarding();
  const [authenticatedResult, setAuthenticatedResult] =
    useState<AuthenticatedDetailResult | null>(null);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    const userId = onboardingState.userId;
    if (onboardingState.mode !== "supabase" || !userId) return;

    let active = true;
    getAuthenticatedStockDetailData(code)
      .then((data) => {
        if (active) setAuthenticatedResult({ userId, code, data });
      })
      .catch((error: unknown) => {
        if (!active) return;
        setAuthenticatedResult({
          userId,
          code,
          error:
            error instanceof Error
              ? error.message
              : "종목 상세 데이터를 불러오지 못했습니다.",
        });
      });

    return () => {
      active = false;
    };
  }, [code, onboardingState.mode, onboardingState.userId, requestVersion]);

  const currentResult =
    authenticatedResult &&
    authenticatedResult.userId === onboardingState.userId &&
    authenticatedResult.code === code
      ? authenticatedResult
      : null;
  const data = currentResult?.data ?? initialData;
  const error = currentResult?.error ?? "";
  const loading =
    onboardingState.mode === "supabase" && !currentResult?.data && !error;

  function retry() {
    setAuthenticatedResult(null);
    setRequestVersion((version) => version + 1);
  }

  return (
    <StockDetailView
      {...data}
      loading={loading}
      dataError={error}
      onRetry={retry}
    />
  );
}
