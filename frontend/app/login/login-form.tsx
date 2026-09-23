"use client";

import { useState, type FormEvent } from "react";
import { useOnboarding } from "@/app/components/onboarding-provider";
import {
  requestMagicLink,
  signInWithPassword,
  signUpWithPassword,
  startDemoSession,
} from "@/lib/auth";
import { isSupabaseConfigured } from "@/lib/supabase";
import { SERVICE_NAME, SERVICE_TAGLINE } from "@/lib/brand";

type AccountTab = "signin" | "signup";

export default function LoginForm() {
  const { refresh } = useOnboarding();
  // 이메일 계정 기능은 Supabase 환경변수가 있을 때만. 데모 계정은 항상 쓸 수 있다.
  const accountAvailable = isSupabaseConfigured();
  const [tab, setTab] = useState<AccountTab>("signin");
  const [emailOpen, setEmailOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  async function run(task: () => Promise<void>) {
    setSubmitting(true);
    setError("");
    setNotice("");
    try {
      await task();
    } catch (taskError) {
      setError(taskError instanceof Error ? taskError.message : "요청을 처리하지 못했습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  function submitAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void run(async () => {
      if (tab === "signin") {
        await signInWithPassword(email.trim(), password);
        await refresh(true);
        return;
      }
      const { needsEmailConfirmation } = await signUpWithPassword(email.trim(), password);
      if (needsEmailConfirmation) {
        setNotice(`${email.trim()}로 확인 메일을 보냈어요. 메일의 링크를 누르면 로그인됩니다.`);
        return;
      }
      await refresh(true);
    });
  }

  function sendMagicLink() {
    void run(async () => {
      await requestMagicLink(email.trim());
      setNotice(`${email.trim()}로 로그인 링크를 보냈어요. 메일의 링크를 열면 이어집니다.`);
    });
  }

  function startDemo() {
    void run(async () => {
      startDemoSession();
      await refresh(true);
    });
  }

  const field =
    "h-11 w-full rounded-md bg-field px-3.5 text-sm font-normal text-ink outline-none focus:bg-white focus:ring-2 focus:ring-brand/30";

  return (
    <main className="grid min-h-dvh place-items-center bg-page px-4 py-10">
      <section className="surface flex w-full max-w-[400px] flex-col gap-6 px-6 py-9 sm:px-9">
        <div className="flex flex-col gap-2 text-center">
          <h1 className="text-3xl font-semibold">
            <span className="text-brand">{SERVICE_NAME}</span> 로그인
          </h1>
          <p className="m-0 text-sm text-body">{SERVICE_TAGLINE}</p>
        </div>

        {!accountAvailable ? (
          <p className="m-0 rounded-md bg-field px-4 py-3 text-xs text-muted">
            이 배포에는 계정 기능이 아직 연결되지 않았어요. 아래 데모로 모든 화면을 둘러볼 수 있어요.
          </p>
        ) : !emailOpen ? (
          <button type="button" onClick={() => setEmailOpen(true)} className="btn-primary w-full">
            이메일로 시작
          </button>
        ) : (
          <div className="flex flex-col gap-4">
            <h2 className="sr-only">이메일로 시작</h2>
            <div role="tablist" aria-label="계정" className="segmented grid grid-cols-2">
              {(
                [
                  ["signin", "로그인"],
                  ["signup", "처음이에요"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={tab === id}
                  onClick={() => {
                    setTab(id);
                    setError("");
                    setNotice("");
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <form onSubmit={submitAccount} className="flex flex-col gap-3">
              <label className="flex flex-col gap-1.5 text-xs text-muted">
                이메일
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="name@example.com"
                  autoComplete="email"
                  required
                  autoFocus
                  className={field}
                />
              </label>
              <label className="flex flex-col gap-1.5 text-xs text-muted">
                비밀번호
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder={tab === "signup" ? "6자 이상" : ""}
                  autoComplete={tab === "signup" ? "new-password" : "current-password"}
                  minLength={6}
                  required
                  className={field}
                />
              </label>
              <button type="submit" disabled={submitting} className="btn-primary w-full">
                {submitting ? "처리 중" : tab === "signin" ? "로그인" : "가입하고 시작"}
              </button>
              <button
                type="button"
                onClick={sendMagicLink}
                disabled={submitting || !email.trim()}
                className="btn-text self-center text-xs disabled:cursor-not-allowed disabled:text-muted"
              >
                비밀번호 없이 로그인 링크 받기
              </button>
            </form>
          </div>
        )}

        {notice && (
          <p role="status" className="m-0 rounded-md bg-field px-4 py-3 text-sm text-body">
            {notice}
          </p>
        )}
        {error && (
          <p role="alert" className="m-0 text-sm text-danger">
            {error}
          </p>
        )}

        <div className="flex flex-col gap-2">
          <button type="button" onClick={startDemo} disabled={submitting} className="btn-secondary w-full">
            데모로 둘러보기
          </button>
          <p className="m-0 text-center text-xs text-muted">
            가입 없이 예시 사용자(김민지)로 둘러봐요. 수치는 예시예요.
          </p>
        </div>
      </section>
    </main>
  );
}
