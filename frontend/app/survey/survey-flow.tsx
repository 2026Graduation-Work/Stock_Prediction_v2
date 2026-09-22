"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  applyAdjustments,
  AVOIDED_ASSET_DESCRIPTIONS,
  AVOIDED_ASSET_LABELS,
  EXPERIENCE_CHOICES,
  threeAxisSummary,
  type ExperienceChoice,
  type SurveyAnswers,
} from "@/lib/profiling-rules";
import { BIT_LABEL, BIT_SUMMARY, classifyBit } from "@/lib/profiling/bit";
import {
  answersFromPattern,
  AXES,
  LIKERT_OPTIONS,
  questionsForMode,
  scoreStyleAxes,
  type AxisDefinition,
  type StyleQuestion,
} from "@/lib/profiling/style-scoring";
import { saveProfile } from "@/lib/save-profile";
import type { ProfilingOutput, RiskFlag, StyleAxes, StyleAxisId } from "@/lib/types";
import { useOnboarding } from "../components/onboarding-provider";
import SignOutButton from "../components/sign-out-button";

// 한 화면 최대 2문항. 축마다 3문항이라 축 하나가 두 화면(2 + 1)이 된다.
const QUESTIONS_PER_PAGE = 2;
const DRAFT_KEY = "signallab.survey-draft.v1";

type Page =
  | { kind: "style"; axis: AxisDefinition; axisIndex: number; questions: StyleQuestion[]; lastOfAxis: boolean }
  | { kind: "experience" }
  | { kind: "avoided" }
  | { kind: "freeText" };

const QUICK_QUESTIONS = questionsForMode("quick");
const PAGES: Page[] = [
  ...AXES.flatMap((axis, axisIndex) => {
    const questions = QUICK_QUESTIONS.filter(
      (question) => question.type === "likert" && question.axis === axis.id,
    );
    const pages: Page[] = [];
    for (let start = 0; start < questions.length; start += QUESTIONS_PER_PAGE) {
      pages.push({
        kind: "style",
        axis,
        axisIndex,
        questions: questions.slice(start, start + QUESTIONS_PER_PAGE),
        lastOfAxis: start + QUESTIONS_PER_PAGE >= questions.length,
      });
    }
    return pages;
  }),
  { kind: "experience" },
  { kind: "avoided" },
  { kind: "freeText" },
];
const FINAL_STEPS = ["experience", "avoided", "freeText"] as const;
const FINAL_STEP_LABEL = {
  experience: "투자 경험",
  avoided: "제외할 종목 유형",
  freeText: "요즘 걱정되는 점",
} as const;

interface Draft {
  page: number;
  style: Record<string, number>;
  experience: ExperienceChoice | "";
  avoided: RiskFlag[];
  freeText: string;
}

const EMPTY_DRAFT: Draft = { page: 0, style: {}, experience: "", avoided: [], freeText: "" };

// 데모 응답: 김민지와 비슷한 추종형 패턴(축 방향 강도 -2~+2)
const DEMO_DRAFT: Draft = {
  page: PAGES.length - 1,
  style: answersFromPattern(
    {
      market_participation: 0,
      loss_tolerance: -1,
      turnover: -1,
      concentration: 0,
      rule_adherence: 0,
      information_reliance: 0,
      urgency: 1,
      drawdown_reaction: 1,
    },
    "quick",
  ) as Record<string, number>,
  experience: "6m_2y",
  avoided: ["spac", "managed_stock"],
  freeText: "남들 다 버는데 나만 뒤처지는 것 같아서 조급해요. 그래도 마이너스 나면 잠을 못 자요.",
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

// https·localhost는 secure context라 randomUUID가 항상 있다.
const createSessionId = () => `s_${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`;

function readDraft(): Draft | null {
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(DRAFT_KEY) ?? "null");
    if (!parsed || typeof parsed !== "object") return null;
    const draft = { ...EMPTY_DRAFT, ...(parsed as Partial<Draft>) };
    draft.page = Math.min(Math.max(0, Math.trunc(draft.page) || 0), PAGES.length - 1);
    return draft;
  } catch {
    return null;
  }
}

function writeDraft(draft: Draft | null) {
  try {
    if (draft) window.localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    else window.localStorage.removeItem(DRAFT_KEY);
  } catch {
    // 저장이 막힌 브라우저(시크릿 모드 등)에서는 중간 저장만 건너뛴다.
  }
}

// 축을 다 답하면 보여 주는 한 줄. 판단이 아니라 응답 방향만 알려 준다.
function axisFeedback(axis: AxisDefinition, style: Record<string, number>): string | null {
  const answered = QUICK_QUESTIONS.filter(
    (question) => question.type === "likert" && question.axis === axis.id,
  ).every(({ id }) => style[id] !== undefined);
  if (!answered) return null;
  const ratio = scoreStyleAxes(style, "quick").axes.find(({ axis_id }) => axis_id === axis.id)!.ratio;
  if (ratio <= -0.2) return `지금까지 답을 보면 '${axis.negative_label}' 쪽이에요.`;
  if (ratio >= 0.2) return `지금까지 답을 보면 '${axis.positive_label}' 쪽이에요.`;
  return `지금까지 답을 보면 '${axis.negative_label}'과 '${axis.positive_label}' 사이 중간이에요.`;
}

export default function SurveyFlow() {
  const router = useRouter();
  const { state: onboardingState } = useOnboarding();
  const demo = onboardingState.mode === "demo";
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [restored, setRestored] = useState(false);
  const [result, setResult] = useState<ProfilingOutput | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // 중간 저장 불러오기. localStorage는 브라우저에서만 읽을 수 있어 마운트 후에 한 번 읽는다.
  useEffect(() => {
    const stored = readDraft();
    if (!stored) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- 외부 저장소에서 한 번 복원
    setDraft(stored);
    setRestored(true);
  }, []);

  function update(next: Partial<Draft>) {
    setDraft((current) => {
      const merged = { ...current, ...next };
      writeDraft(merged);
      return merged;
    });
  }

  const page = PAGES[draft.page];
  const canContinue =
    page.kind === "style"
      ? page.questions.every(({ id }) => draft.style[id] !== undefined)
      : page.kind === "experience"
        ? draft.experience !== ""
        : true;

  function payload(adjusted?: Partial<Record<StyleAxisId, number>>): SurveyAnswers {
    return {
      user_id: "u_minji_001",
      session_id: result?.session_id ?? createSessionId(),
      timestamp: result?.timestamp ?? new Date().toISOString(),
      style: draft.style,
      experience: draft.experience as ExperienceChoice,
      avoided_assets: draft.avoided,
      free_text: draft.freeText,
      ...(adjusted && Object.keys(adjusted).length ? { adjusted_axes: adjusted } : {}),
      preferred_sectors: ["semiconductor", "healthcare"],
      // 보유 종목 입력 화면이 아직 없다. 데모 계정만 김민지 보유 종목을 쓰고, 실제 계정은 비워 둔다.
      ...(demo ? { portfolio: DEMO_PORTFOLIO } : {}),
      investment_amount_krw: 500000,
      action_intent: "buy_consideration",
      market_regime_hint: "high_volatility",
      benchmark_index: "KOSPI",
    };
  }

  async function requestProfile(body: SurveyAnswers): Promise<ProfilingOutput> {
    const response = await fetch("/api/profiling", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const parsed = (await response.json()) as ProfilingOutput | { error: string };
    if (!response.ok) {
      throw new Error("error" in parsed ? parsed.error : "프로필을 만들지 못했습니다.");
    }
    return parsed as ProfilingOutput;
  }

  async function run(task: () => Promise<void>) {
    setSubmitting(true);
    setError("");
    try {
      await task();
    } catch (taskError) {
      setError(taskError instanceof Error ? taskError.message : "프로필을 만들지 못했습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  function advance() {
    if (!canContinue) return;
    if (draft.page === PAGES.length - 1) {
      void run(async () => setResult(await requestProfile(payload())));
      return;
    }
    update({ page: draft.page + 1 });
  }

  // 확인 단계에서 확정해야 저장한다. 조정했으면 조정값으로 다시 계산해 저장한다.
  function confirm(adjusted: Partial<Record<StyleAxisId, number>>) {
    void run(async () => {
      const profile = Object.keys(adjusted).length
        ? await requestProfile(payload(adjusted))
        : result!;
      await saveProfile(profile, onboardingState.mode);
      writeDraft(null);
      setResult(profile);
      setSaved(true);
    });
  }

  function restart() {
    writeDraft(null);
    setDraft(EMPTY_DRAFT);
    setResult(null);
    setSaved(false);
    setRestored(false);
    setError("");
  }

  return (
    <div className="min-h-screen bg-page">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex min-h-16 w-full max-w-[1080px] items-center gap-2.5 px-4 py-2 sm:h-16 sm:gap-3 sm:px-8 sm:py-0">
          <Link href="/" className="flex items-center gap-2.5 text-ink hover:no-underline">
            <span className="text-lg font-semibold text-brand">시그널랩</span>
          </Link>
          <span className="h-5 w-px bg-line" />
          <span className="whitespace-nowrap text-sm font-semibold text-body">투자 성향 설문</span>
          <div className="ml-auto flex items-center gap-2">
            {!result && demo && (
              <button
                type="button"
                onClick={() => {
                  update(DEMO_DRAFT);
                  setError("");
                }}
                className="rounded-lg px-3 py-2 text-xs font-medium text-brand hover:bg-brand-soft"
              >
                <span className="hidden sm:inline">데모 응답 불러오기</span>
                <span className="sm:hidden">데모 불러오기</span>
              </button>
            )}
            <SignOutButton />
          </div>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-[920px] flex-col px-5 py-8 sm:px-8 sm:py-12">
        {!result ? (
          <QuestionPage
            draft={draft}
            page={page}
            restored={restored}
            canContinue={canContinue}
            submitting={submitting}
            error={error}
            onUpdate={update}
            onBack={() => update({ page: Math.max(0, draft.page - 1) })}
            onNext={advance}
            onRestart={restart}
          />
        ) : (
          <ResultView
            result={result}
            saved={saved}
            submitting={submitting}
            error={error}
            onConfirm={confirm}
            onRestart={restart}
            onDashboard={() => router.push("/")}
          />
        )}
      </main>
    </div>
  );
}

function ProgressBar({ draft, page }: { draft: Draft; page: Page }) {
  const finalIndex = page.kind === "style" ? -1 : FINAL_STEPS.indexOf(page.kind);
  const label =
    page.kind === "style"
      ? `성향 문항 ${page.axisIndex + 1}/${AXES.length} · ${page.axis.section}`
      : `마무리 ${finalIndex + 1}/${FINAL_STEPS.length} · ${FINAL_STEP_LABEL[page.kind]}`;
  const currentSegment = page.kind === "style" ? page.axisIndex : AXES.length + finalIndex;
  return (
    <div className="border-b border-line-soft px-6 py-5 sm:px-10">
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-brand">{label}</span>
          <span className="ml-auto text-xs tabular-nums text-muted">
            {draft.page + 1} / {PAGES.length} 화면
          </span>
        </div>
        <div
          className="grid gap-1.5"
          style={{ gridTemplateColumns: `repeat(${AXES.length + FINAL_STEPS.length}, minmax(0, 1fr))` }}
          role="progressbar"
          aria-label="설문 진행률"
          aria-valuemin={1}
          aria-valuemax={PAGES.length}
          aria-valuenow={draft.page + 1}
        >
          {Array.from({ length: AXES.length + FINAL_STEPS.length }, (_, index) => (
            <span
              key={index}
              className={`h-1.5 rounded ${index <= currentSegment ? "bg-brand-accent" : "bg-track"} ${
                index === AXES.length ? "ml-1" : ""
              }`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function QuestionPage({
  draft,
  page,
  restored,
  canContinue,
  submitting,
  error,
  onUpdate,
  onBack,
  onNext,
  onRestart,
}: {
  draft: Draft;
  page: Page;
  restored: boolean;
  canContinue: boolean;
  submitting: boolean;
  error: string;
  onUpdate: (next: Partial<Draft>) => void;
  onBack: () => void;
  onNext: () => void;
  onRestart: () => void;
}) {
  const last = draft.page === PAGES.length - 1;
  const feedback = page.kind === "style" && page.lastOfAxis ? axisFeedback(page.axis, draft.style) : null;

  return (
    <section className="overflow-hidden surface shadow-lift">
      <ProgressBar draft={draft} page={page} />
      <div className="flex min-h-[480px] flex-col px-6 py-8 sm:px-10 sm:py-10">
        {restored && draft.page > 0 && (
          <div className="mb-6 flex items-center gap-3 rounded-lg bg-brand-soft px-4 py-3 text-sm text-brand-deep">
            저장해 둔 응답을 불러왔어요. 이어서 답하면 됩니다.
            <button type="button" onClick={onRestart} className="ml-auto text-xs font-medium hover:underline">
              처음부터 하기
            </button>
          </div>
        )}

        {page.kind === "style" && (
          <>
            <span className="mb-2 text-xs font-semibold text-brand">{page.axis.section}</span>
            <p className="mb-6 text-sm leading-6 text-muted">
              {page.axis.help}. 맞고 틀린 답은 없어요. 요즘의 나와 가장 가까운 쪽을 골라 주세요.
            </p>
            <div className="flex flex-col gap-8">
              {page.questions.map((question) => (
                <fieldset key={question.id} className="flex flex-col gap-3">
                  <legend className="mb-3 text-lg font-semibold leading-[1.5] text-ink sm:text-xl">
                    {question.text}
                  </legend>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-5">
                    {LIKERT_OPTIONS.map((option) => {
                      const selected = draft.style[question.id] === option.value;
                      return (
                        <label
                          key={option.value}
                          className={`flex min-h-12 cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2.5 text-sm font-semibold transition-colors sm:flex-col sm:justify-center sm:text-center ${
                            selected
                              ? "border-brand bg-brand-soft text-brand-deep"
                              : "border-edge bg-white text-body hover:border-brand hover:bg-field"
                          }`}
                        >
                          <input
                            type="radio"
                            name={question.id}
                            checked={selected}
                            onChange={() =>
                              onUpdate({ style: { ...draft.style, [question.id]: option.value } })
                            }
                            className="size-4 flex-none accent-[var(--color-brand)]"
                          />
                          {option.label}
                        </label>
                      );
                    })}
                  </div>
                </fieldset>
              ))}
            </div>
            {feedback && (
              <p role="status" className="mt-6 rounded-lg bg-field px-4 py-3 text-sm font-semibold text-body">
                {feedback}
              </p>
            )}
          </>
        )}

        {page.kind === "experience" && (
          <>
            <span className="mb-3 text-xs font-semibold text-brand">투자 경험</span>
            <h1 className="text-2xl font-semibold leading-[1.4] text-ink sm:text-3xl">
              직접 투자한 경험은 얼마나 되나요?
            </h1>
            <p className="mt-2 text-sm leading-6 text-muted">
              주식이나 ETF를 직접 사고판 기간을 기준으로 골라 주세요.
            </p>
            <div className="mt-8 flex flex-col gap-2.5">
              {EXPERIENCE_CHOICES.map((choice) => (
                <ChoiceRow
                  key={choice.id}
                  type="radio"
                  name="experience"
                  label={choice.label}
                  selected={draft.experience === choice.id}
                  onChange={() => onUpdate({ experience: choice.id })}
                />
              ))}
            </div>
          </>
        )}

        {page.kind === "avoided" && (
          <>
            <span className="mb-3 text-xs font-semibold text-brand">제외할 종목 유형 (선택)</span>
            <h1 className="text-2xl font-semibold leading-[1.4] text-ink sm:text-3xl">
              목록에서 빼고 싶은 종목 유형이 있나요?
            </h1>
            <p className="mt-2 text-sm leading-6 text-muted">
              직접 고른 항목만 목록에서 빠져요. 성향 점수로는 종목을 빼지 않아요. 없으면 그냥
              넘어가도 됩니다.
            </p>
            <div className="mt-8 flex flex-col gap-2.5">
              {(Object.entries(AVOIDED_ASSET_LABELS) as [RiskFlag, string][]).map(([flag, label]) => (
                <ChoiceRow
                  key={flag}
                  type="checkbox"
                  name="avoided"
                  label={label}
                  detail={AVOIDED_ASSET_DESCRIPTIONS[flag]}
                  selected={draft.avoided.includes(flag)}
                  onChange={() =>
                    onUpdate({
                      avoided: draft.avoided.includes(flag)
                        ? draft.avoided.filter((item) => item !== flag)
                        : [...draft.avoided, flag],
                    })
                  }
                />
              ))}
            </div>
          </>
        )}

        {page.kind === "freeText" && (
          <>
            <span className="mb-3 text-xs font-semibold text-brand">요즘 걱정되는 점 (선택)</span>
            <h1 className="text-2xl font-semibold leading-[1.4] text-ink sm:text-3xl">
              투자하면서 요즘 가장 걱정되는 점이 있다면 적어 주세요.
            </h1>
            <p className="mt-2 text-sm leading-6 text-muted">
              점수 계산에는 쓰지 않고, 결과를 설명할 때 참고로만 보관해요. 비워 둬도 됩니다.
            </p>
            <textarea
              value={draft.freeText}
              onChange={(event) => onUpdate({ freeText: event.target.value })}
              rows={6}
              maxLength={500}
              placeholder="예: 남들보다 수익이 뒤처질까 조급하지만 손실도 많이 걱정돼요."
              className="mt-8 w-full resize-none rounded-lg border border-edge bg-field px-4 py-3 text-sm leading-6 text-ink outline-none placeholder:text-muted focus:border-brand focus:bg-white"
            />
          </>
        )}

        {error && (
          <p role="alert" className="mt-4 text-sm font-semibold text-danger">
            {error}
          </p>
        )}

        <div className="mt-auto flex items-center gap-3 pt-8">
          <button
            type="button"
            onClick={onBack}
            disabled={draft.page === 0 || submitting}
            className="h-11 rounded-lg border border-edge bg-white px-5 text-sm font-medium text-body hover:bg-field disabled:cursor-not-allowed disabled:opacity-40"
          >
            이전
          </button>
          <span className="text-xs text-muted">답은 자동으로 저장돼요</span>
          <button
            type="button"
            onClick={onNext}
            disabled={!canContinue || submitting}
            className="btn-primary ml-auto min-w-[112px]"
          >
            {submitting ? "계산 중" : last ? "결과 확인" : "다음"}
          </button>
        </div>
      </div>
    </section>
  );
}

function ChoiceRow({
  type,
  name,
  label,
  detail,
  selected,
  onChange,
}: {
  type: "radio" | "checkbox";
  name: string;
  label: string;
  detail?: string;
  selected: boolean;
  onChange: () => void;
}) {
  return (
    <label
      className={`flex min-h-[56px] cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 text-sm font-semibold transition-colors ${
        selected
          ? "border-brand bg-brand-soft text-brand-deep"
          : "border-edge bg-white text-body hover:border-brand hover:bg-field"
      }`}
    >
      <input type={type} name={name} checked={selected} onChange={onChange} className="size-4 flex-none accent-[var(--color-brand)]" />
      <span className="flex flex-col gap-0.5">
        <span>{label}</span>
        {detail && <span className="text-xs font-normal text-muted">{detail}</span>}
      </span>
    </label>
  );
}

function AxisGauge({
  label,
  value,
  caption,
  left,
  right,
}: {
  label: string;
  value: number;
  caption: string;
  left: string;
  right: string;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <div className="flex items-baseline gap-2">
        <span className="text-sm font-medium text-ink">{label}</span>
        <span className="ml-auto text-xl font-semibold tabular-nums text-ink">{value}</span>
      </div>
      <div className="h-2 overflow-hidden rounded bg-track">
        <div className="h-full rounded bg-brand-accent" style={{ width: `${value}%` }} />
      </div>
      <span className="flex justify-between text-2xs text-muted">
        <span>0 {left}</span>
        <span>100 {right}</span>
      </span>
      <span className="text-xs text-muted">{caption}</span>
    </div>
  );
}

const HORIZON_LABEL = { short: "단기", mid: "중기", long: "장기" } as const;

function ResultView({
  result,
  saved,
  submitting,
  error,
  onConfirm,
  onRestart,
  onDashboard,
}: {
  result: ProfilingOutput;
  saved: boolean;
  submitting: boolean;
  error: string;
  onConfirm: (adjusted: Partial<Record<StyleAxisId, number>>) => void;
  onRestart: () => void;
  onDashboard: () => void;
}) {
  const [adjusting, setAdjusting] = useState(false);
  const [adjusted, setAdjusted] = useState<Partial<Record<StyleAxisId, number>>>({});
  const scored = result.style_axes!;
  const styleAxes: StyleAxes = applyAdjustments(scored, adjusted);
  const bit = classifyBit(styleAxes);
  const summary = threeAxisSummary(styleAxes);
  const changed = Object.keys(adjusted).length > 0;
  const avoidedLabels = result.constraints.avoided_assets.map((asset) => AVOIDED_ASSET_LABELS[asset]);

  return (
    <section className="overflow-hidden surface shadow-lift">
      <div className="border-b border-line bg-sig-sp-tint px-6 py-7 sm:px-10">
        <span className="text-xs font-semibold text-brand">
          {saved ? "프로필 저장 완료" : "진단 결과 · 아직 저장 전이에요"}
        </span>
        <h1 data-bit-type={bit.lowConfidence ? "low_confidence" : bit.type} className="mt-2 text-3xl font-semibold text-ink sm:text-3xl">
          {bit.lowConfidence ? "유형 확인 중" : BIT_LABEL[bit.type]}
        </h1>
        <p className="mt-1 text-sm font-semibold text-muted">
          {bit.lowConfidence
            ? "몇몇 질문의 답이 서로 엇갈려 유형을 단정하지 않았어요. 다시 답하거나 아래에서 직접 조정할 수 있어요."
            : BIT_SUMMARY[bit.type]}
        </p>
        <p className="mt-3 text-xs leading-5 text-muted">
          행동투자자 유형(BIT, Pompian)에서 착안한 분류예요. 금융회사의 투자자 등급과는 다른 것이고,
          정보를 보여 주는 순서와 주의 안내에만 쓰며 종목을 거르지 않아요.
        </p>
      </div>

      <div className="px-6 py-8 sm:px-10 sm:py-10">
        <div className="grid gap-8 md:grid-cols-3">
          <AxisGauge
            label="위험 감수"
            value={summary.riskTaking}
            caption="손실을 견디는 정도와 소수 종목 집중 선호를 합친 값"
            left="원금 보전"
            right="수익 기회"
          />
          <AxisGauge
            label="흔들림 민감도"
            value={summary.sensitivity}
            caption="조급함·하락 시 이탈·주변 의견 추종을 합친 값"
            left="차분함"
            right="흔들림 큼"
          />
          <AxisGauge
            label="투자 기간"
            value={summary.horizonScore}
            caption={`${HORIZON_LABEL[summary.horizon]} 보유 성향 · 보유 기간과 회전 문항 기준`}
            left="장기 보유"
            right="단기 매매"
          />
        </div>

        {(result.contradictions?.length ?? 0) > 0 && (
          <div className="mt-8 flex flex-col gap-2 rounded-lg bg-field px-4 py-3">
            <span className="text-sm font-medium text-body">답변 중 서로 부딪히는 부분이 있어요</span>
            {result.contradictions!.map((item) => (
              <p key={item.id} className="m-0 text-sm leading-6 text-body">
                {item.observation} <span className="text-body">→ {item.follow_up_question}</span>
              </p>
            ))}
          </div>
        )}

        <div className="mt-8 border-t border-line-soft pt-6">
          <div className="flex flex-wrap items-center gap-2">
            <span className="mr-2 text-sm font-medium text-ink">제외할 종목 유형</span>
            {avoidedLabels.length ? (
              avoidedLabels.map((label) => (
                <span
                  key={label}
                  className="rounded-full border border-sig-sn-tint bg-sig-sn-tint px-3 py-1.5 text-xs font-medium text-sig-sn"
                >
                  {label}
                </span>
              ))
            ) : (
              <span className="text-sm text-muted">선택한 항목 없음</span>
            )}
          </div>
        </div>

        {adjusting && !saved && (
          <div id="style-axes-adjust" className="mt-8 flex flex-col gap-3 rounded-lg border border-line bg-field px-5 py-5">
            <p className="m-0 text-sm text-body">
              결과가 나와 다르다고 느껴지는 축만 옮겨 주세요. 유형과 위의 요약이 바로 다시 계산돼요.
            </p>
            <div className="grid grid-cols-1 gap-x-8 gap-y-3 md:grid-cols-2">
              {AXES.map((axis) => {
                const ratio = styleAxes.axes.find(({ axis_id }) => axis_id === axis.id)!.ratio;
                return (
                  <label key={axis.id} className="flex flex-col gap-1 text-xs">
                    <span className="flex items-center gap-2">
                      <strong className="text-ink">{axis.section}</strong>
                      <span className="ml-auto font-medium tabular-nums text-ink">
                        {ratio > 0 ? "+" : ""}
                        {ratio.toFixed(2)}
                      </span>
                    </span>
                    <input
                      type="range"
                      min={-1}
                      max={1}
                      step={0.05}
                      value={ratio}
                      aria-label={axis.section}
                      onChange={(event) =>
                        setAdjusted((current) => ({ ...current, [axis.id]: Number(event.target.value) }))
                      }
                      className="accent-brand"
                    />
                    <span className="flex justify-between text-2xs text-muted">
                      <span>{axis.negative_label}</span>
                      <span>{axis.positive_label}</span>
                    </span>
                  </label>
                );
              })}
            </div>
          </div>
        )}

        {error && (
          <p role="alert" className="mt-4 text-sm font-semibold text-danger">
            {error}
          </p>
        )}

        {saved ? (
          <div className="mt-8 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-end">
            <span className="text-sm text-muted sm:mr-auto">
              저장했어요. 대시보드와 종목 화면이 이 결과를 기준으로 정보를 보여 줘요.
            </span>
            <button
              type="button"
              onClick={onDashboard}
              className="btn-primary"
            >
              대시보드로 이동
            </button>
          </div>
        ) : (
          <div className="mt-8 flex flex-col gap-3 border-t border-line-soft pt-6">
            <span className="text-base font-semibold text-ink">이 결과가 나와 맞나요?</span>
            <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={onRestart}
                disabled={submitting}
                className="h-11 rounded-lg border border-edge bg-white px-5 text-sm font-medium text-body hover:bg-field"
              >
                다시 응답하기
              </button>
              {adjusting ? (
                <button
                  type="button"
                  onClick={() => {
                    setAdjusted({});
                    setAdjusting(false);
                  }}
                  disabled={submitting}
                  className="h-11 rounded-lg border border-edge bg-white px-5 text-sm font-medium text-body hover:bg-field"
                >
                  조정 취소
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => setAdjusting(true)}
                  aria-controls="style-axes-adjust"
                  className="btn-secondary"
                >
                  직접 조정하기
                </button>
              )}
              <button
                type="button"
                onClick={() => onConfirm(changed ? adjusted : {})}
                disabled={submitting}
                className="btn-primary"
              >
                {submitting ? "저장 중" : changed ? "조정한 값으로 저장" : "네, 이대로 저장"}
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
