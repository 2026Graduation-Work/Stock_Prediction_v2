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

type AccountTab = "signin" | "signup";

export default function LoginForm() {
  const { refresh } = useOnboarding();
  // 이메일 계정 기능은 Supabase 환경변수가 있을 때만. 데모 계정은 항상 쓸 수 있다.
  const accountAvailable = isSupabaseConfigured();
  const [tab, setTab] = useState<AccountTab>("signin");
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

  return (
    <div className="min-h-screen bg-page">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex h-16 w-full max-w-[1080px] items-center gap-2.5 px-5 sm:px-8">
          <span className="grid size-8 place-items-center rounded-lg bg-brand text-sm font-semibold text-white">
            S
          </span>
          <span className="text-lg font-semibold text-ink">시그널랩</span>
        </div>
      </header>

      <main className="mx-auto grid min-h-[calc(100vh-65px)] w-full max-w-[1080px] place-items-center px-5 py-10 sm:px-8">
        <section className="w-full max-w-[440px] surface px-6 py-8 shadow-lift sm:px-9 sm:py-10">
          <h1 className="text-3xl font-semibold text-ink">시그널랩 로그인</h1>
          <p className="mt-2 text-sm leading-6 text-muted">
            처음 투자하는 사람도 종목을 판단할 근거를 쉽게 확인하도록 돕는 서비스예요. 설문으로 내 투자
            성향을 알면 정보를 보여 주는 순서와 주의 안내가 나에게 맞춰집니다.
          </p>

          <div className="mt-8">
            <h2 className="text-sm font-semibold text-ink">이메일로 시작</h2>
            {accountAvailable ? (
              <>
                <div role="tablist" aria-label="계정" className="mt-3 grid grid-cols-2 gap-1 rounded-lg bg-track p-1">
                  {(
                    [
                      ["signin", "로그인"],
                      ["signup", "처음이에요 (가입)"],
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
                      className={`h-9 rounded-md text-xs font-medium ${
                        tab === id ? "bg-white text-ink shadow-sm" : "text-muted hover:text-ink"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <form onSubmit={submitAccount} className="mt-4 flex flex-col gap-3">
                  <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
                    이메일
                    <input
                      type="email"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      placeholder="name@example.com"
                      autoComplete="email"
                      required
                      className="h-11 w-full rounded-lg border border-edge bg-field px-3.5 text-sm font-normal text-ink outline-none placeholder:text-muted focus:border-brand focus:bg-white"
                    />
                  </label>
                  <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
                    비밀번호
                    <input
                      type="password"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      placeholder={tab === "signup" ? "6자 이상" : ""}
                      autoComplete={tab === "signup" ? "new-password" : "current-password"}
                      minLength={6}
                      required
                      className="h-11 w-full rounded-lg border border-edge bg-field px-3.5 text-sm font-normal text-ink outline-none placeholder:text-muted focus:border-brand focus:bg-white"
                    />
                  </label>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="h-11 w-full rounded-lg bg-brand px-5 text-sm font-medium text-white hover:bg-brand-deep disabled:cursor-not-allowed disabled:bg-ghost"
                  >
                    {submitting ? "처리 중" : tab === "signin" ? "로그인" : "가입하고 시작"}
                  </button>
                  <button
                    type="button"
                    onClick={sendMagicLink}
                    disabled={submitting || !email.trim()}
                    className="self-start text-xs font-medium text-brand hover:text-brand-deep disabled:cursor-not-allowed disabled:text-ghost"
                  >
                    비밀번호 없이 로그인 링크 받기
                  </button>
                </form>
              </>
            ) : (
              <p className="mt-2 rounded-lg border border-line bg-field px-4 py-3 text-xs leading-5 text-muted">
                이 배포에는 계정 기능이 아직 연결되지 않았어요. 아래 데모 계정으로 모든 화면을 둘러볼 수
                있습니다.
              </p>
            )}
          </div>

          {notice && (
            <p role="status" className="mt-4 rounded-lg border bg-brand-soft px-4 py-3 text-sm leading-6 text-brand">
              {notice}
            </p>
          )}
          {error && (
            <p role="alert" className="mt-4 text-sm font-semibold text-danger">
              {error}
            </p>
          )}

          <div className="my-7 flex items-center gap-3 text-xs text-muted">
            <span className="h-px flex-1 bg-line" />
            또는
            <span className="h-px flex-1 bg-line" />
          </div>

          <button
            type="button"
            onClick={startDemo}
            disabled={submitting}
            className="h-11 w-full rounded-lg border border-brand bg-white px-5 text-sm font-medium text-brand hover:bg-brand-soft disabled:cursor-not-allowed disabled:opacity-50"
          >
            데모 계정으로 둘러보기
          </button>
          <p className="mt-2 text-xs leading-5 text-muted">
            가입 없이 예시 사용자(김민지)로 둘러봐요. 화면의 수치는 예시이고, 설문 결과는 이 브라우저에만
            저장됩니다.
          </p>

          <p className="mt-8 border-t border-line-soft pt-5 text-xs leading-5 text-muted">
            처음 들어오면 투자 성향 설문(약 3분)을 마친 뒤 대시보드로 이동합니다.
          </p>
        </section>
      </main>
    </div>
  );
}
