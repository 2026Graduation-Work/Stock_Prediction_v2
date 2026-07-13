"use client";

import type { ProfilingOutput } from "./types";

export const PROFILE_STORAGE_KEY = "signallab.ips-profile.v1";
export const PROFILE_UPDATED_EVENT = "signallab:profile-updated";

export async function saveProfile(profile: ProfilingOutput): Promise<void> {
  // Supabase 연결 시 이 경계만 ips_profiles.upsert 호출로 교체한다.
  // 현재 MVP는 동일 브라우저에서 설문→대시보드 흐름을 검증하도록 로컬에 보관한다.
  window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile));
  window.dispatchEvent(new Event(PROFILE_UPDATED_EVENT));
}

export function getSavedProfileSnapshot(): string | null {
  return window.localStorage.getItem(PROFILE_STORAGE_KEY);
}

export function getServerProfileSnapshot(): null {
  return null;
}

export function subscribeToSavedProfile(onStoreChange: () => void) {
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
    return JSON.parse(serialized) as ProfilingOutput;
  } catch {
    return null;
  }
}
