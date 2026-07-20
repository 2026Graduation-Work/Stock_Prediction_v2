"use client";

import type { User } from "@supabase/supabase-js";
import {
  PROFILE_STORAGE_KEY,
  PROFILE_UPDATED_EVENT,
  parseSavedProfile,
} from "./save-profile";
import { getSupabaseClient, isSupabaseConfigured } from "./supabase";

const DEMO_SESSION_STORAGE_KEY = "signallab.demo-session.v1";
export const AUTH_UPDATED_EVENT = "signallab:auth-updated";

export type OnboardingStatus =
  | "loading"
  | "signed_out"
  | "needs_survey"
  | "ready"
  | "error";

export interface OnboardingState {
  status: OnboardingStatus;
  mode: "demo" | "supabase";
  userId?: string;
  displayName?: string;
  error?: string;
}

interface DemoSession {
  userId: string;
  displayName: string;
  signedInAt: string;
}

export function getAuthMode(): OnboardingState["mode"] {
  return isSupabaseConfigured() ? "supabase" : "demo";
}

export async function resolveOnboardingState(): Promise<OnboardingState> {
  const client = getSupabaseClient();
  if (!client) return resolveDemoOnboardingState();

  const { data: sessionData, error: sessionError } = await client.auth.getSession();
  if (sessionError) {
    throw new Error(`로그인 세션 확인 실패: ${sessionError.message}`);
  }
  if (!sessionData.session) {
    clearSavedProfile();
    return { status: "signed_out", mode: "supabase" };
  }

  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) {
    throw new Error(
      `로그인 사용자 확인 실패: ${userError?.message ?? "사용자 정보가 없습니다."}`,
    );
  }

  return resolveSupabaseProfile(userData.user);
}

async function resolveSupabaseProfile(user: User): Promise<OnboardingState> {
  const client = getSupabaseClient();
  if (!client) return { status: "signed_out", mode: "supabase" };

  const { data: appUser, error: appUserError } = await client
    .from("users")
    .select("id, display_name")
    .eq("auth_user_id", user.id)
    .maybeSingle();
  if (appUserError) {
    throw new Error(`사용자 프로필 확인 실패: ${appUserError.message}`);
  }

  const displayName = displayNameFor(user, appUser?.display_name);
  if (!appUser) {
    clearSavedProfile();
    return {
      status: "needs_survey",
      mode: "supabase",
      userId: user.id,
      displayName,
    };
  }

  const { data: profile, error: profileError } = await client
    .from("ips_profiles")
    .select("profile_payload")
    .eq("user_id", appUser.id)
    .maybeSingle();
  if (profileError) {
    throw new Error(`투자 성향 확인 실패: ${profileError.message}`);
  }
  if (!profile) {
    clearSavedProfile();
    return {
      status: "needs_survey",
      mode: "supabase",
      userId: user.id,
      displayName,
    };
  }

  syncSavedProfile(profile.profile_payload);
  return {
    status: "ready",
    mode: "supabase",
    userId: user.id,
    displayName,
  };
}

function resolveDemoOnboardingState(): OnboardingState {
  const session = readDemoSession();
  if (!session) return { status: "signed_out", mode: "demo" };

  const profile = parseSavedProfile(
    window.localStorage.getItem(PROFILE_STORAGE_KEY),
  );
  return {
    status: profile ? "ready" : "needs_survey",
    mode: "demo",
    userId: session.userId,
    displayName: session.displayName,
  };
}

export function startDemoSession(): void {
  const session: DemoSession = {
    userId: "demo_minji",
    displayName: "김민지",
    signedInAt: new Date().toISOString(),
  };
  window.localStorage.setItem(DEMO_SESSION_STORAGE_KEY, JSON.stringify(session));
  window.dispatchEvent(new Event(AUTH_UPDATED_EVENT));
}

export async function requestMagicLink(email: string): Promise<void> {
  const client = getSupabaseClient();
  if (!client) throw new Error("Supabase 환경변수가 설정되지 않았습니다.");

  const { error } = await client.auth.signInWithOtp({
    email,
    options: {
      emailRedirectTo: `${window.location.origin}/login`,
    },
  });
  if (error) throw new Error(`로그인 링크 전송 실패: ${error.message}`);
}

export async function signOut(): Promise<void> {
  const client = getSupabaseClient();
  let signOutError: Error | null = null;
  if (client) {
    const { error } = await client.auth.signOut({ scope: "local" });
    if (error) signOutError = new Error(`로그아웃 실패: ${error.message}`);
  }

  window.localStorage.removeItem(DEMO_SESSION_STORAGE_KEY);
  clearSavedProfile();
  window.dispatchEvent(new Event(AUTH_UPDATED_EVENT));

  if (signOutError) throw signOutError;
}

export function subscribeToAuthChanges(onChange: () => void): () => void {
  const onStorage = (event: StorageEvent) => {
    if (
      event.key === DEMO_SESSION_STORAGE_KEY ||
      event.key === PROFILE_STORAGE_KEY
    ) {
      onChange();
    }
  };
  const onUpdated = () => onChange();

  window.addEventListener("storage", onStorage);
  window.addEventListener(AUTH_UPDATED_EVENT, onUpdated);
  window.addEventListener(PROFILE_UPDATED_EVENT, onUpdated);

  const client = getSupabaseClient();
  const subscription = client?.auth.onAuthStateChange(() => {
    window.setTimeout(onChange, 0);
  }).data.subscription;

  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(AUTH_UPDATED_EVENT, onUpdated);
    window.removeEventListener(PROFILE_UPDATED_EVENT, onUpdated);
    subscription?.unsubscribe();
  };
}

function readDemoSession(): DemoSession | null {
  try {
    const serialized = window.localStorage.getItem(DEMO_SESSION_STORAGE_KEY);
    if (!serialized) return null;
    const value: unknown = JSON.parse(serialized);
    if (!isRecord(value)) return null;
    if (
      typeof value.userId !== "string" ||
      typeof value.displayName !== "string" ||
      typeof value.signedInAt !== "string"
    ) {
      return null;
    }
    return value as unknown as DemoSession;
  } catch {
    return null;
  }
}

function displayNameFor(user: User, storedName?: string | null): string {
  if (storedName?.trim()) return storedName.trim();
  const fullName = user.user_metadata.full_name;
  if (typeof fullName === "string" && fullName.trim()) return fullName.trim();
  return user.email?.split("@")[0] || "사용자";
}

function syncSavedProfile(value: unknown): void {
  const serialized = JSON.stringify(value);
  if (!parseSavedProfile(serialized)) {
    clearSavedProfile();
    return;
  }
  if (window.localStorage.getItem(PROFILE_STORAGE_KEY) === serialized) return;
  window.localStorage.setItem(PROFILE_STORAGE_KEY, serialized);
  window.dispatchEvent(new Event(PROFILE_UPDATED_EVENT));
}

function clearSavedProfile(): void {
  if (!window.localStorage.getItem(PROFILE_STORAGE_KEY)) return;
  window.localStorage.removeItem(PROFILE_STORAGE_KEY);
  window.dispatchEvent(new Event(PROFILE_UPDATED_EVENT));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
