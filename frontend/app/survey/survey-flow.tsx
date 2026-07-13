"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  AVOIDED_ASSET_LABELS,
  horizonCodeForScore,
  horizonScoreForMonths,
  type SurveyAnswers,
} from "@/lib/profiling-rules";
import { saveProfile } from "@/lib/save-profile";
import type { ProfilingOutput, RiskFlag } from "@/lib/types";

type QuestionId = "Q1" | "Q2" | "Q3" | "Q4" | "Q5" | "Q6" | "Q7";

interface DraftAnswers {
  Q1: string;
  Q2: string;
  Q3: string;
  Q4: string[];
  Q5: string;
  Q6: RiskFlag[];
  Q7: string;
}

interface ChoiceQuestion {
  id: Exclude<QuestionId, "Q7">;
  eyebrow: string;
  title: string;
  description: string;
  type: "single" | "multi";
  choices: { id: string; label: string; detail?: string }[];
}

interface TextQuestion {
  id: "Q7";
  eyebrow: string;
  title: string;
  description: string;
  type: "text";
}

type SurveyQuestion = ChoiceQuestion | TextQuestion;

const QUESTIONS: SurveyQuestion[] = [
  {
    id: "Q1",
    eyebrow: "위험 감수",
    title: "투자한 종목이 15% 하락했다면 어떻게 하시겠어요?",
    description: "실제로 가장 가까운 행동을 골라주세요.",
    type: "single",
    choices: [
      { id: "Q1_A", label: "더 떨어지기 전에 바로 정리해요." },
      { id: "Q1_B", label: "며칠 지켜보고 원인을 확인한 뒤 결정해요." },
      { id: "Q1_C", label: "판단이 그대로라면 추가 매수를 검토해요." },
    ],
  },
  {
    id: "Q2",
    eyebrow: "투자 기간",
    title: "이 투자금은 언제 다시 사용할 가능성이 큰가요?",
    description: "자금이 묶여 있어도 괜찮은 기간을 기준으로 답해주세요.",
    type: "single",
    choices: [
      { id: "Q2_A", label: "1년 안에 사용할 수 있어요." },
      { id: "Q2_B", label: "3~5년 뒤 사용할 계획이에요." },
      { id: "Q2_C", label: "10년 이상 투자해도 괜찮아요." },
    ],
  },
  {
    id: "Q3",
    eyebrow: "심리 민감도",
    title: "주변 종목이 단기간에 크게 올랐다는 소식을 들으면 어떤가요?",
    description: "수익 기회를 놓쳤다고 느꼈을 때의 반응을 골라주세요.",
    type: "single",
    choices: [
      { id: "Q3_A", label: "나만 놓칠까 봐 빨리 따라 사고 싶어져요." },
      { id: "Q3_B", label: "부럽지만 내 기준에 맞는지 먼저 확인해요." },
      { id: "Q3_C", label: "이미 오른 종목보다 다른 기회를 찾아봐요." },
    ],
  },
  {
    id: "Q4",
    eyebrow: "판단 근거",
    title: "투자 아이디어를 주로 어디에서 얻나요?",
    description: "평소 참고하는 곳을 모두 선택해주세요.",
    type: "multi",
    choices: [
      { id: "Q4_A", label: "유튜브·온라인 커뮤니티" },
      { id: "Q4_B", label: "친구·지인" },
      { id: "Q4_C", label: "뉴스·공시" },
      { id: "Q4_D", label: "재무제표·기업 분석" },
    ],
  },
  {
    id: "Q5",
    eyebrow: "투자 경험",
    title: "직접 투자한 경험은 얼마나 되나요?",
    description: "주식이나 ETF를 직접 매매한 기간을 기준으로 골라주세요.",
    type: "single",
    choices: [
      { id: "Q5_A", label: "6개월 미만" },
      { id: "Q5_B", label: "6개월~2년" },
      { id: "Q5_C", label: "2~5년" },
      { id: "Q5_D", label: "5년 이상" },
    ],
  },
  {
    id: "Q6",
    eyebrow: "회피 설정",
    title: "추천에서 반드시 제외할 종목 유형을 선택해 주세요.",
    description: "직접 선택한 항목만 추천 후보에서 제외됩니다. 복수 선택할 수 있어요.",
    type: "multi",
    choices: (Object.entries(AVOIDED_ASSET_LABELS) as [RiskFlag, string][]).map(
      ([id, label]) => ({ id, label }),
    ),
  },
  {
    id: "Q7",
    eyebrow: "현재 마음",
    title: "투자하면서 요즘 가장 걱정되는 점을 적어주세요.",
    description: "점수 계산에는 사용하지 않고 결과 설명을 위한 참고 정보로 보관합니다.",
    type: "text",
  },
];

const EMPTY_ANSWERS: DraftAnswers = {
  Q1: "",
  Q2: "",
  Q3: "",
  Q4: [],
  Q5: "",
  Q6: [],
  Q7: "",
};

const MINJI_DEMO: DraftAnswers = {
  Q1: "Q1_B",
  Q2: "Q2_B",
  Q3: "Q3_A",
  Q4: ["Q4_A"],
  Q5: "Q5_B",
  Q6: ["spac", "managed_stock"],
  Q7: "남들 다 버는데 나만 뒤처지는 것 같아서 조급해요. 그래도 마이너스 나면 잠을 못 자요.",
};

const DEMO_PORTFOLIO: ProfilingOutput["portfolio"] = {
  holdings: [
    { ticker: "005930", name: "삼성전자", quantity: 15, avg_buy_price: 71200 },
    { ticker: "035720", name: "카카오", quantity: 8, avg_buy_price: 48500 },
    { ticker: "068270", name: "셀트리온", quantity: 3, avg_buy_price: 182000 },
    { ticker: "005380", name: "현대차", quantity: 5, avg_buy_price: 235000 },
  ],
  watchlist: ["000660", "035420", "051910"],
};

function createSessionId() {
  const uuid = globalThis.crypto?.randomUUID?.();
  const fallback = `${Date.now().toString(36)}${Math.floor(
    globalThis.performance?.now?.() ?? 0,
  ).toString(36)}`;
  const token = (uuid ?? fallback).replaceAll("-", "").slice(0, 12).padEnd(12, "0");
  return `s_${token}`;
}

function AxisGauge({
  label,
  value,
  caption,
  tone,
}: {
  label: string;
  value: number;
  caption: string;
  tone: "brand" | "amber" | "green";
}) {
  const color = {
    brand: "bg-brand",
    amber: "bg-[#d28a22]",
    green: "bg-[#16856b]",
  }[tone];
  return (
    <div className="flex min-w-0 flex-col gap-2.5">
      <div className="flex items-baseline gap-2">
        <span className="text-sm font-bold text-ink">{label}</span>
        <span className="ml-auto text-xl font-extrabold tabular-nums text-ink">{value}</span>
      </div>
      <div className="h-2 overflow-hidden rounded bg-track">
        <div className={`h-full rounded ${color}`} style={{ width: `${value}%` }} />
      </div>
      <span className="text-xs text-muted">{caption}</span>
    </div>
  );
}

export default function SurveyFlow() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<DraftAnswers>(EMPTY_ANSWERS);
  const [result, setResult] = useState<ProfilingOutput | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const question = QUESTIONS[step];

  const currentValue = answers[question.id];
  const canContinue =
    question.id === "Q6" ||
    question.id === "Q7" ||
    (Array.isArray(currentValue) ? currentValue.length > 0 : currentValue.length > 0);

  function selectSingle(questionId: QuestionId, choiceId: string) {
    setAnswers((current) => ({ ...current, [questionId]: choiceId }));
  }

  function toggleMulti(questionId: "Q4" | "Q6", choiceId: string) {
    setAnswers((current) => {
      const selected = current[questionId] as string[];
      return {
        ...current,
        [questionId]: selected.includes(choiceId)
          ? selected.filter((id) => id !== choiceId)
          : [...selected, choiceId],
      };
    });
  }

  function loadDemoAnswers() {
    setAnswers(MINJI_DEMO);
    setError("");
  }

  async function submitSurvey() {
    setSubmitting(true);
    setError("");
    const payload: SurveyAnswers = {
      user_id: "u_minji_001",
      session_id: createSessionId(),
      timestamp: new Date().toISOString(),
      Q1: answers.Q1 as SurveyAnswers["Q1"],
      Q2: answers.Q2 as SurveyAnswers["Q2"],
      Q3: answers.Q3 as SurveyAnswers["Q3"],
      Q4: answers.Q4 as SurveyAnswers["Q4"],
      Q5: answers.Q5 as SurveyAnswers["Q5"],
      Q6: answers.Q6,
      Q7: answers.Q7,
      preferred_sectors: ["semiconductor", "healthcare"],
      portfolio: DEMO_PORTFOLIO,
      investment_amount_krw: 500000,
      action_intent: "buy_consideration",
      market_regime_hint: "high_volatility",
      benchmark_index: "KOSPI",
    };

    try {
      const response = await fetch("/api/profiling", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = (await response.json()) as ProfilingOutput | { error: string };
      if (!response.ok) {
        throw new Error("error" in body ? body.error : "프로필을 만들지 못했습니다.");
      }
      const profile = body as ProfilingOutput;
      await saveProfile(profile);
      setResult(profile);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "프로필을 만들지 못했습니다.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  function advance() {
    if (!canContinue) return;
    if (step === QUESTIONS.length - 1) {
      void submitSurvey();
      return;
    }
    setStep((current) => current + 1);
  }

  function restart() {
    setAnswers(EMPTY_ANSWERS);
    setResult(null);
    setStep(0);
    setError("");
  }

  return (
    <div className="min-h-screen bg-page">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex h-16 w-full max-w-[1080px] items-center gap-3 px-5 sm:px-8">
          <Link href="/" className="flex items-center gap-2.5 text-ink hover:no-underline">
            <span className="grid size-7 place-items-center rounded-lg bg-brand text-sm font-extrabold text-white">
              S
            </span>
            <span className="text-[17px] font-extrabold">시그널랩</span>
          </Link>
          <span className="h-5 w-px bg-line" />
          <span className="text-sm font-semibold text-body">투자 성향 설문</span>
          {!result && (
            <button
              type="button"
              onClick={loadDemoAnswers}
              className="ml-auto rounded-lg px-3 py-2 text-xs font-bold text-brand hover:bg-brand-soft"
            >
              데모 응답 불러오기
            </button>
          )}
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-[920px] flex-col px-5 py-8 sm:px-8 sm:py-12">
        {!result ? (
          <section className="overflow-hidden rounded-lg border border-line bg-white shadow-[0_12px_34px_rgba(27,36,52,0.07)]">
            <div className="border-b border-line-soft px-6 py-5 sm:px-10">
              <div className="flex items-center gap-4">
                <span className="text-xs font-bold tabular-nums text-brand">
                  {step + 1} / {QUESTIONS.length}
                </span>
                <div className="grid flex-1 grid-cols-7 gap-1.5" aria-label="설문 진행률">
                  {QUESTIONS.map((item, index) => (
                    <span
                      key={item.id}
                      className={`h-1.5 rounded ${index <= step ? "bg-brand" : "bg-track"}`}
                    />
                  ))}
                </div>
              </div>
            </div>

            <div className="flex min-h-[480px] flex-col px-6 py-8 sm:px-10 sm:py-10">
              <span className="mb-3 text-xs font-extrabold text-brand">{question.eyebrow}</span>
              <h1 className="max-w-[680px] text-2xl font-extrabold leading-[1.4] text-ink sm:text-[28px]">
                {question.title}
              </h1>
              <p className="mt-2 text-sm leading-6 text-muted">{question.description}</p>

              <div className="mt-8 flex flex-col gap-2.5">
                {question.type !== "text" &&
                  question.choices.map((choice) => {
                    const selected = Array.isArray(currentValue)
                      ? (currentValue as readonly string[]).includes(choice.id)
                      : currentValue === choice.id;
                    return (
                      <label
                        key={choice.id}
                        className={`flex min-h-[56px] cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 text-sm font-semibold transition-colors ${
                          selected
                            ? "border-brand bg-brand-soft text-brand-deep"
                            : "border-edge bg-white text-body hover:border-brand hover:bg-field"
                        }`}
                      >
                        <input
                          type={question.type === "multi" ? "checkbox" : "radio"}
                          name={question.id}
                          checked={selected}
                          onChange={() =>
                            question.type === "multi"
                              ? toggleMulti(question.id as "Q4" | "Q6", choice.id)
                              : selectSingle(question.id, choice.id)
                          }
                          className="size-4 flex-none accent-[#2f5fd0]"
                        />
                        <span>{choice.label}</span>
                      </label>
                    );
                  })}

                {question.type === "text" && (
                  <textarea
                    value={answers.Q7}
                    onChange={(event) =>
                      setAnswers((current) => ({ ...current, Q7: event.target.value }))
                    }
                    rows={7}
                    maxLength={500}
                    placeholder="예: 남들보다 수익이 뒤처질까 조급하지만 손실도 많이 걱정돼요."
                    className="w-full resize-none rounded-lg border border-edge bg-field px-4 py-3 text-sm leading-6 text-ink outline-none placeholder:text-faint focus:border-brand focus:bg-white"
                  />
                )}
              </div>

              {error && (
                <p role="alert" className="mt-4 text-sm font-semibold text-[#b42318]">
                  {error}
                </p>
              )}

              <div className="mt-auto flex items-center gap-3 pt-8">
                <button
                  type="button"
                  onClick={() => setStep((current) => Math.max(0, current - 1))}
                  disabled={step === 0 || submitting}
                  className="h-11 rounded-lg border border-edge bg-white px-5 text-sm font-bold text-body hover:bg-field disabled:cursor-not-allowed disabled:opacity-40"
                >
                  이전
                </button>
                {question.id === "Q6" && answers.Q6.length === 0 && (
                  <span className="text-xs text-faint">선택 없이 진행할 수 있어요</span>
                )}
                <button
                  type="button"
                  onClick={advance}
                  disabled={!canContinue || submitting}
                  className="ml-auto h-11 min-w-[112px] rounded-lg bg-brand px-5 text-sm font-bold text-white hover:bg-brand-deep disabled:cursor-not-allowed disabled:bg-ghost"
                >
                  {submitting
                    ? "계산 중"
                    : step === QUESTIONS.length - 1
                      ? "결과 확인"
                      : "다음"}
                </button>
              </div>
            </div>
          </section>
        ) : (
          <ResultSummary
            result={result}
            onRestart={restart}
            onDashboard={() => router.push("/")}
          />
        )}
      </main>
    </div>
  );
}

function ResultSummary({
  result,
  onRestart,
  onDashboard,
}: {
  result: ProfilingOutput;
  onRestart: () => void;
  onDashboard: () => void;
}) {
  const riskScore = Math.round(result.investor_profile.risk_tolerance * 100);
  const fomoScore = Math.round(result.psychological_state.fomo_index * 100);
  const horizonScore = horizonScoreForMonths(
    result.investor_profile.time_horizon_months,
  );
  const horizonCode = horizonCodeForScore(horizonScore);
  const stable = result.investor_profile.profile_type === "stable";
  const avoidedLabels = result.constraints.avoided_assets.map(
    (asset) => AVOIDED_ASSET_LABELS[asset],
  );

  return (
    <section className="overflow-hidden rounded-lg border border-line bg-white shadow-[0_12px_34px_rgba(27,36,52,0.07)]">
      <div className="border-b border-line bg-[#f7fbf9] px-6 py-7 sm:px-10">
        <span className="text-xs font-extrabold text-[#16856b]">프로필 생성 완료</span>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-end">
          <h1 className="text-[28px] font-extrabold text-ink sm:text-[32px]">
            {stable ? "안정추구형" : "수익추구형"}
          </h1>
          <span className="mb-1 text-sm font-semibold text-muted">
            {stable ? "신중하게 기준을 지키는 투자자" : "기회를 적극적으로 탐색하는 투자자"}
          </span>
        </div>
      </div>

      <div className="px-6 py-8 sm:px-10 sm:py-10">
        <div className="grid gap-8 md:grid-cols-3">
          <AxisGauge label="위험 감수" value={riskScore} caption="risk_tolerance" tone="brand" />
          <AxisGauge label="심리 민감도" value={fomoScore} caption="fomo_index" tone="amber" />
          <AxisGauge
            label="투자 기간"
            value={horizonScore}
            caption={`${horizonCode} · ${result.investor_profile.time_horizon_months}개월`}
            tone="green"
          />
        </div>

        <div className="mt-10 border-t border-line-soft pt-7">
          <div className="flex flex-wrap items-center gap-2">
            <span className="mr-2 text-sm font-bold text-ink">회피 설정</span>
            {avoidedLabels.length ? (
              avoidedLabels.map((label) => (
                <span
                  key={label}
                  className="rounded-full border border-[#f0c9c5] bg-[#fff5f3] px-3 py-1.5 text-xs font-bold text-[#a83a31]"
                >
                  {label}
                </span>
              ))
            ) : (
              <span className="text-sm text-muted">선택한 회피 항목 없음</span>
            )}
          </div>
          <p className="mt-3 text-xs leading-5 text-muted">
            선택한 유형은 추천 후보에서 제외되며, 그 외 성향 점수는 종목 제거가 아닌 정렬과 설명에만 사용됩니다.
          </p>
        </div>

        <details className="mt-7 border-t border-line-soft pt-5">
          <summary className="cursor-pointer text-sm font-bold text-brand">
            생성된 프로필 JSON 보기
          </summary>
          <pre className="mt-3 max-h-[320px] overflow-auto rounded-lg bg-[#172033] p-4 text-xs leading-5 text-[#e8edf7]">
            {JSON.stringify(result, null, 2)}
          </pre>
        </details>

        <div className="mt-8 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onRestart}
            className="h-11 rounded-lg border border-edge bg-white px-5 text-sm font-bold text-body hover:bg-field"
          >
            다시 응답하기
          </button>
          <button
            type="button"
            onClick={onDashboard}
            className="h-11 rounded-lg bg-brand px-5 text-sm font-bold text-white hover:bg-brand-deep"
          >
            대시보드로 이동
          </button>
        </div>
      </div>
    </section>
  );
}
