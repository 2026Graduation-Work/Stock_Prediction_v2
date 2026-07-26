"use client";

import { useState, type FormEvent } from "react";
import { useOnboarding } from "@/app/components/onboarding-provider";
import {
  getAuthMode,
  requestMagicLink,
  startDemoSession,
} from "@/lib/auth";

export default function LoginForm() {
  const { refresh } = useOnboarding();
  const mode = getAuthMode();
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  async function submitEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await requestMagicLink(email.trim());
      setSent(true);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "로그인 링크를 보내지 못했습니다.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function startDemo() {
    setSubmitting(true);
    setError("");
    try {
      startDemoSession();
      await refresh(true);
    } catch (startError) {
      setError(
        startError instanceof Error
          ? startError.message
          : "데모 로그인을 시작하지 못했습니다.",
      );
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-page">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex h-16 w-full max-w-[1080px] items-center gap-2.5 px-5 sm:px-8">
          <span className="grid size-8 place-items-center rounded-lg bg-brand text-sm font-extrabold text-white">
            S
          </span>
          <span className="text-[17px] font-extrabold text-ink">시그널랩</span>
        </div>
      </header>

      <main className="mx-auto grid min-h-[calc(100vh-65px)] w-full max-w-[1080px] place-items-center px-5 py-10 sm:px-8">
        <section className="w-full max-w-[440px] rounded-lg border border-line bg-white px-6 py-8 shadow-[0_12px_34px_rgba(27,36,52,0.07)] sm:px-9 sm:py-10">
          <span className="text-xs font-extrabold text-brand">SIGN IN</span>
          <h1 className="mt-2 text-[28px] font-extrabold text-ink">
            시그널랩 로그인
          </h1>
          <p className="mt-2 text-sm leading-6 text-muted">
            나의 투자 성향과 근거가 연결된 신호를 확인합니다.
          </p>

          {mode === "supabase" ? (
            sent ? (
              <div className="mt-8 rounded-lg border border-[#b8dfd4] bg-[#f1faf7] p-4">
                <p className="text-sm font-bold text-[#126b58]">이메일을 확인해 주세요</p>
                <p className="mt-1 text-sm leading-6 text-body">
                  {email}로 보낸 로그인 링크를 열면 자동으로 이어집니다.
                </p>
                <button
                  type="button"
                  onClick={() => setSent(false)}
                  className="mt-3 text-xs font-bold text-brand hover:text-brand-deep"
                >
                  다른 이메일 사용
                </button>
              </div>
            ) : (
              <form onSubmit={submitEmail} className="mt-8">
                <label htmlFor="email" className="text-sm font-bold text-ink">
                  이메일
                </label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="name@example.com"
                  autoComplete="email"
                  required
                  className="mt-2 h-11 w-full rounded-lg border border-edge bg-field px-3.5 text-sm text-ink outline-none placeholder:text-faint focus:border-brand focus:bg-white"
                />
                <button
                  type="submit"
                  disabled={submitting}
                  className="mt-4 h-11 w-full rounded-lg bg-brand px-5 text-sm font-bold text-white hover:bg-brand-deep disabled:cursor-not-allowed disabled:bg-ghost"
                >
                  {submitting ? "전송 중" : "로그인 링크 받기"}
                </button>
              </form>
            )
          ) : (
            <div className="mt-8">
              <div className="rounded-lg border border-line bg-field px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="size-2 rounded-full bg-[#16856b]" />
                  <span className="text-sm font-bold text-ink">데모 환경</span>
                </div>
                <p className="mt-1.5 text-xs leading-5 text-muted">
                  로그인과 설문 결과는 이 브라우저에만 저장됩니다.
                </p>
              </div>
              <button
                type="button"
                onClick={() => void startDemo()}
                disabled={submitting}
                className="mt-4 h-11 w-full rounded-lg bg-brand px-5 text-sm font-bold text-white hover:bg-brand-deep disabled:cursor-not-allowed disabled:bg-ghost"
              >
                {submitting ? "시작 중" : "김민지 데모로 시작"}
              </button>
            </div>
          )}

          {error && (
            <p role="alert" className="mt-4 text-sm font-semibold text-[#b42318]">
              {error}
            </p>
          )}

          <p className="mt-8 border-t border-line-soft pt-5 text-xs leading-5 text-faint">
            처음 로그인한 사용자는 투자 성향 설문을 완료한 뒤 대시보드로 이동합니다.
          </p>
        </section>
      </main>
    </div>
  );
}
