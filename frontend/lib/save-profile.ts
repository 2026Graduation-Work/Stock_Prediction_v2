"use client";

import type { ProfilingOutput } from "./types";

export const PROFILE_STORAGE_KEY = "signallab.ips-profile.v1";
export const PROFILE_UPDATED_EVENT = "signallab:profile-updated";

export async function saveProfile(profile: ProfilingOutput): Promise<void> {
  if (typeof window === "undefined") return;
  // Supabase 연결 시 이 경계만 ips_profiles.upsert 호출로 교체한다.
  // 현재 MVP는 동일 브라우저에서 설문→대시보드 흐름을 검증하도록 로컬에 보관한다.
  window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile));
  window.dispatchEvent(new Event(PROFILE_UPDATED_EVENT));
}

export function getSavedProfileSnapshot(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(PROFILE_STORAGE_KEY);
}

export function getServerProfileSnapshot(): null {
  return null;
}

export function subscribeToSavedProfile(onStoreChange: () => void) {
  if (typeof window === "undefined") return () => undefined;
  window.addEventListener("storage", onStoreChange);
  window.addEventListener(PROFILE_UPDATED_EVENT, onStoreChange);
  return () => {
    window.removeEventListener("storage", onStoreChange);
    window.removeEventListener(PROFILE_UPDATED_EVENT, onStoreChange);
  };
}

export function parseSavedProfile(serialized: string | null): ProfilingOutput | null {
  if (!serialized) return null;
  try {
    const parsed: unknown = JSON.parse(serialized);
    return isProfilingOutput(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function isProfilingOutput(value: unknown): value is ProfilingOutput {
  if (!isRecord(value)) return false;
  const investor = value.investor_profile;
  const psychology = value.psychological_state;
  const constraints = value.constraints;
  const meta = value.meta;
  if (
    !isRecord(investor) ||
    !isRecord(psychology) ||
    !isRecord(constraints) ||
    !isRecord(meta)
  ) {
    return false;
  }

  const validRiskFlags = new Set([
    "spac",
    "managed_stock",
    "low_liquidity",
    "penny_stock",
    "high_volatility",
    "preferred_stock",
  ]);
  return (
    typeof value.timestamp === "string" &&
    !Number.isNaN(Date.parse(value.timestamp)) &&
    typeof investor.risk_tolerance === "number" &&
    Number.isFinite(investor.risk_tolerance) &&
    typeof investor.time_horizon_months === "number" &&
    Number.isFinite(investor.time_horizon_months) &&
    (investor.profile_type === "stable" || investor.profile_type === "aggressive") &&
    typeof psychology.fomo_index === "number" &&
    Number.isFinite(psychology.fomo_index) &&
    Array.isArray(constraints.avoided_assets) &&
    constraints.avoided_assets.every(
      (asset) => typeof asset === "string" && validRiskFlags.has(asset),
    ) &&
    meta.schema_version === "1.0.0"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
