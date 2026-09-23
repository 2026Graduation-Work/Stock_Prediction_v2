"use client";

// 종목 상세의 성향 기반 영역: 나에게 맞춘 체크포인트 · 판단 근거 4탭 · 계산 근거.
// 성향은 소프트 틸트다. 탭 순서와 체크포인트에만 쓰고 종목을 거르지 않는다.
// 연구 질문 ② "성향 기반 표시"는 탭 순서(data-card-order)로 보존한다.

import { useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import {
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { FINANCIAL_TERM, TERM } from "@/lib/copy-glossary";
import { STYLE_AXIS_IDS } from "@/lib/profiling-rules";
import {
  BIT_LABEL,
  BIT_TYPES,
  classifyBit,
  presetStyleAxes,
  type BitResult,
  type BitType,
  type CardId,
} from "@/lib/profiling/bit";
import { SCREEN_GUIDE_NOTICE, selectNudges } from "@/lib/profiling/nudges";
import {
  combinedProvenance,
  periodsOverlap,
  pricePeriod,
  riskSnapshot,
  sentimentPeriod,
  toNudgeMarket,
  type ContributionCategory,
  type ContributionSignal,
  type FinancialSnapshot,
  type HoldingWeight,
  type SentimentData,
  type StockInsights,
  type SupplyDemandDay,
} from "@/lib/providers";
import { CHART } from "@/lib/chart-colors";
import type { DataProvenance, PredictionReason, StockDetail, StyleAxes, StyleAxisId } from "@/lib/types";
import SourceChip from "./source-chip";

// 극성은 lib/profiling/style-questions.json axes와 같다.
const AXIS_META: Record<StyleAxisId, { name: string; negative: string; positive: string }> = {
  market_participation: { name: "시장과 내 목표", negative: "시장 수익률 참여", positive: "내 목표 우선" },
  loss_tolerance: { name: "손실 감내", negative: "원금 보전", positive: "수익 기회" },
  turnover: { name: "보유 기간", negative: "장기 보유", positive: "단기 매매" },
  concentration: { name: "집중과 분산", negative: "폭넓은 분산", positive: "소수 집중" },
  rule_adherence: { name: "계획 운용", negative: "사전 규칙 준수", positive: "상황별 재량" },
  information_reliance: { name: "판단의 근거", negative: "본인 판단", positive: "시장·타인 추종" },
  urgency: { name: "기회를 대하는 태도", negative: "여유", positive: "조급함" },
  drawdown_reaction: { name: "하락에 대한 반응", negative: "하락 시 유지", positive: "하락 시 이탈" },
};

const BIAS_MODE_LABEL = {
  emotional: "감정적 편향이 두드러지는 구간",
  cognitive: "인지적 편향이 두드러지는 구간",
} as const;

// 8축 진단 결과가 없을 때의 순서
const DEFAULT_CARD_ORDER: readonly CardId[] = [
  "nudge",
  "contribution",
  "supply",
  "sentiment",
  "risk",
  "financial",
];

type TabId = "market" | "supply" | "financial" | "contribution";

// 유형별 카드 순서(bit.ts CARD_ORDER) → 판단 근거 탭. 넛지는 체크포인트로, 변동성은 시장 분위기 탭으로 간다.
const CARD_TO_TAB: Partial<Record<CardId, TabId>> = {
  sentiment: "market",
  risk: "market",
  supply: "supply",
  financial: "financial",
  contribution: "contribution",
};

const TAB_META: Record<TabId, { label: string; question: string; why: string }> = {
  market: {
    label: TERM.market,
    question: "요즘 이 종목을 둘러싼 분위기는 어떤가요?",
    why: "뉴스 분위기와 가격 흔들림은 짧은 기간 가격을 크게 움직이곤 해요. 분위기에 휩쓸린 판단인지 한 번 더 보게 해 줘요.",
  },
  supply: {
    label: TERM.supply,
    question: "최근 누가 이 종목을 사고팔았나요?",
    why: "개인·외국인·기관이 실제로 거래한 기록이에요. 누가 어느 쪽으로 움직였는지는 알 수 있지만 이유는 담겨 있지 않아요.",
  },
  financial: {
    label: TERM.financial,
    question: "이 회사는 돈을 잘 벌고 있나요?",
    why: "가격 움직임과 별개로 회사의 기초 체력을 보는 지표예요. 오래 들고 갈 종목이라면 특히 중요해요.",
  },
  contribution: {
    label: TERM.contribution,
    question: "모델은 무엇을 보고 이 신호를 냈나요?",
    why: "모델 신호가 한 가지 근거에 쏠려 있는지 확인할 수 있어요. 그 근거가 내 판단과 맞는지 비교해 보세요.",
  },
};

// 범주는 색이 아니라 라벨로 구분한다. 색은 방향(적 = 오르는 쪽, 청 = 내리는 쪽)에만 쓴다.
const CATEGORY_LABEL: Record<ContributionCategory, string> = {
  technical: "가격 흐름",
  financial: "회사 체력",
  sentiment: "뉴스 분위기",
  supply: "사고판 주체",
};

const SUPPLY_SERIES = [
  { key: "retail", label: "개인" },
  { key: "foreign", label: "외국인" },
  { key: "institution", label: "기관" },
] as const;

const TOOLTIP_STYLE = { border: `1px solid ${CHART.line}`, borderRadius: 8, fontSize: 12 };

const signed = (value: number, digits = 2) => `${value > 0 ? "+" : ""}${value.toFixed(digits)}`;
const signedPercent = (ratio: number) => `${ratio > 0 ? "+" : ""}${(ratio * 100).toFixed(1)}%`;
// 순매수 수량(주). 만 주 단위로 줄여 읽기 쉽게: +5,276,406 → +527.6만 주
const shares = (value: number) =>
  `${value > 0 ? "+" : value < 0 ? "-" : ""}${(Math.abs(value) / 10_000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}만 주`;
const shortDate = (iso: string) => iso.slice(5).replace("-", ".");

// 감성 점수(-1~+1) → 구간 말. 경계는 점수 분포가 아니라 읽기 쉬운 고정 구간이다.
function moodWord(score: number): string {
  if (score >= 0.3) return "긍정적인 편";
  if (score >= 0.1) return "조금 긍정적";
  if (score > -0.1) return "중립에 가까운 편";
  if (score > -0.3) return "조금 부정적";
  return "부정적인 편";
}

export type DemoStyleAxes = ReturnType<typeof useDemoStyleAxes>;

// "다른 유형이라면?": BIT 4유형 프리셋으로 이 화면만 바꿔 본다. DB·localStorage에 쓰지 않는다.
export function useDemoStyleAxes(original: StyleAxes | null) {
  const [viewAs, setViewAs] = useState<BitType | null>(null);
  const styleAxes: StyleAxes | null =
    original && viewAs ? presetStyleAxes(original, viewAs) : original;
  return {
    styleAxes,
    bit: styleAxes ? classifyBit(styleAxes) : null,
    viewAs,
    setViewAs,
  };
}

function Why({ children }: { children: ReactNode }) {
  return (
    <p className="m-0 text-xs text-muted">
      <span className="font-medium text-body">왜 봐야 하나요? </span>
      {children}
    </p>
  );
}

function Unavailable({ children }: { children: ReactNode }) {
  return <p className="m-0 rounded-md bg-field px-4 py-5 text-center text-sm text-muted">{children}</p>;
}

// ── 나에게 맞춘 체크포인트 ───────────────────────────────────

export function Checkpoints({
  demo,
  detail,
  insights,
  holdings,
  extra,
}: {
  demo: DemoStyleAxes;
  detail: StockDetail;
  insights: StockInsights;
  holdings: HoldingWeight[];
  extra: string | null; // 성향 대비 위험도 안내(넛지 외). 있으면 체크포인트 뒤에 붙는다
}) {
  const { bit } = demo;
  const market = toNudgeMarket(detail, insights, holdings);
  const nudges = bit && market ? selectNudges(bit, market) : [];
  const items = [
    ...nudges.map(({ id, text }) => ({ key: id, text })),
    ...(extra ? [{ key: "risk", text: extra }] : []),
  ].slice(0, 2);

  return (
    <section aria-labelledby="checkpoint-title" className="surface flex flex-col gap-4 p-6">
      <div className="flex flex-col gap-1">
        <span className="eyebrow">나에게 맞춘 {TERM.nudge}</span>
        <h2
          id="checkpoint-title"
          data-bit-type={bit ? (bit.lowConfidence ? "low_confidence" : bit.type) : undefined}
          className="text-xl font-semibold"
        >
          {!bit
            ? "성향을 진단하면 나에게 맞춘 확인 거리가 보여요"
            : bit.lowConfidence
              ? "아직 성향을 판단하기엔 응답이 부족해요"
              : `${BIT_LABEL[bit.type]}이라면 이것부터 확인해 보세요`}
        </h2>
        {demo.viewAs && (
          <p className="m-0 flex items-center gap-2 text-xs text-body">
            <span className="size-1.5 rounded-full bg-caution-mark" aria-hidden />
            {BIT_LABEL[demo.viewAs]}의 시선으로 보는 중이에요 · 내 결과가 아니에요
          </p>
        )}
      </div>

      {bit && !market && items.length === 0 ? (
        <p className="m-0 text-sm text-muted">이 종목은 확인 거리를 고르는 데 필요한 데이터가 아직 없어요.</p>
      ) : bit && items.length === 0 ? (
        <p className="m-0 text-sm text-muted">지금 이 종목에서 따로 확인할 점은 없어요.</p>
      ) : (
        <ol className="m-0 flex list-none flex-col gap-3 p-0">
          {items.map((item, index) => (
            <li key={item.key} data-nudge={item.key} className="flex gap-3">
              <span className="flex-none text-sm font-semibold text-muted tabular-nums">{index + 1}</span>
              <p className="m-0 text-base leading-relaxed text-ink">{item.text}</p>
            </li>
          ))}
        </ol>
      )}

      {demo.styleAxes && (
        <details className="disclosure border-t border-line-soft pt-3">
          <summary className="text-xs font-medium text-brand">다른 유형이라면?</summary>
          <p className="mb-2.5 mt-2 text-xs text-muted">
            다른 유형은 같은 종목을 어떤 순서와 확인 거리로 보는지 바꿔 볼 수 있어요. 이 화면에서만 바뀌어요.
          </p>
          <div role="group" aria-label="다른 유형이라면?" className="flex flex-wrap gap-2">
            {[null, ...BIT_TYPES].map((type) => {
              const active = demo.viewAs === type;
              return (
                <button
                  key={type ?? "mine"}
                  type="button"
                  aria-pressed={active}
                  onClick={() => demo.setViewAs(type)}
                  className={`min-h-9 rounded-sm px-3.5 text-xs font-medium ${
                    active ? "bg-brand-soft text-brand" : "bg-track text-body hover:bg-line"
                  }`}
                >
                  {type ? BIT_LABEL[type] : "내 성향"}
                </button>
              );
            })}
          </div>
        </details>
      )}
    </section>
  );
}

// ── 판단 근거 4탭 ────────────────────────────────────────────

export default function EvidenceTabs({
  detail,
  insights,
  demo,
}: {
  detail: StockDetail;
  insights: StockInsights;
  demo: DemoStyleAxes;
}) {
  const order = demo.bit?.cardOrder ?? DEFAULT_CARD_ORDER;
  const tabs = [...new Set(order.map((id) => CARD_TO_TAB[id]).filter((id): id is TabId => Boolean(id)))];
  const [selected, setSelected] = useState<TabId | null>(null);
  const active = selected ?? tabs[0];
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const next = tabs[(tabs.indexOf(active) + step + tabs.length) % tabs.length];
    setSelected(next);
    tabRefs.current[next]?.focus();
  }

  return (
    <section aria-labelledby="evidence-title" className="flex flex-col gap-4">
      <div className="flex flex-col gap-0.5 px-1">
        <span className="eyebrow">판단 근거 4가지 · 내 성향에 맞춘 순서</span>
        <h2 id="evidence-title" className="text-xl font-semibold">
          무엇을 근거로 판단할까요?
        </h2>
      </div>
      <div className="overflow-x-auto [scrollbar-width:none]">
        <div
          role="tablist"
          aria-label="판단 근거"
          data-card-order={order.join(",")}
          onKeyDown={onKeyDown}
          className="segmented"
        >
          {tabs.map((id) => (
            <button
              key={id}
              ref={(node) => {
                tabRefs.current[id] = node;
              }}
              type="button"
              role="tab"
              id={`tab-${id}`}
              aria-selected={active === id}
              aria-controls={`panel-${id}`}
              tabIndex={active === id ? 0 : -1}
              onClick={() => setSelected(id)}
            >
              {TAB_META[id].label}
            </button>
          ))}
        </div>
      </div>
      <div
        role="tabpanel"
        id={`panel-${active}`}
        aria-labelledby={`tab-${active}`}
        data-card={active}
        className="surface flex flex-col gap-4 p-6"
      >
        <h3 className="text-lg font-semibold">{TAB_META[active].question}</h3>
        {active === "market" && <MarketPanel detail={detail} insights={insights} />}
        {active === "supply" && <SupplyPanel supply={insights.supply} provenance={insights.provenance.supply} />}
        {active === "financial" && (
          <FinancialPanel financial={insights.financial} provenance={insights.provenance.financial} />
        )}
        {active === "contribution" && (
          <ContributionPanel
            contributions={insights.contributions}
            reasons={detail.reasons}
            provenance={insights.contributions ? insights.provenance.contributions : detail.provenance}
          />
        )}
        <Why>{TAB_META[active].why}</Why>
      </div>
    </section>
  );
}

function Conclusion({ children }: { children: ReactNode }) {
  return <p className="m-0 text-base text-ink">{children}</p>;
}

function MarketPanel({ detail, insights }: { detail: StockDetail; insights: StockInsights }) {
  const { sentiment, provenance, psychology } = insights;
  const risk = riskSnapshot(detail);
  const prices = pricePeriod(detail);
  const sentimentDates = sentiment ? sentimentPeriod(sentiment) : null;
  const periodMismatch = Boolean(prices && sentimentDates && !periodsOverlap(prices, sentimentDates));
  const latest = sentiment?.days.at(-1);

  return (
    <>
      {latest ? (
        <Conclusion>
          최근 {TERM.sentiment}는 <strong className="font-semibold">{moodWord(latest.score)}</strong>이에요.
        </Conclusion>
      ) : risk ? (
        <Conclusion>
          최근 3개월 {TERM.volatility}은 시장 전체에서 상위 {Math.max(1, Math.round((1 - risk.volatilityPercentile) * 100))}% 수준이에요.
        </Conclusion>
      ) : !psychology ? (
        <Unavailable>이 종목은 분위기를 볼 데이터가 아직 없어요.</Unavailable>
      ) : null}
      {psychology && (
        <p className="m-0 text-sm text-body">
          가격 흐름으로 본 분위기: <strong className="font-semibold text-ink">{psychology.word}</strong>
          <span className="text-muted"> — {psychology.explain}</span>
        </p>
      )}
      {sentiment?.days.length ? <SentimentChart sentiment={sentiment} /> : null}
      {periodMismatch && (
        <p data-period-mismatch className="m-0 flex items-center gap-2 text-xs text-body">
          <span className="size-1.5 rounded-full bg-caution-mark" aria-hidden />
          뉴스 기간({sentimentDates!.start} ~ {sentimentDates!.end})이 주가 기간과 달라요.
        </p>
      )}
      {risk && (
        <dl className="m-0 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Stat label={`${TERM.volatility}(1년 기준)`} value={`${(risk.volatilityAnnual * 100).toFixed(1)}%`} />
          <Stat label="3개월 최고가 대비" value={signedPercent(risk.drawdownFrom3mHigh)} />
          <Stat label="최근 3거래일" value={signedPercent(risk.return3d)} />
        </dl>
      )}
      {sentiment?.headlines.length ? (
        <details className="disclosure text-sm">
          <summary className="text-xs font-medium text-body">대표 기사 {sentiment.headlines.length}건</summary>
          <ul className="m-0 mt-2 flex list-none flex-col gap-1.5 p-0">
            {sentiment.headlines.map((headline) => (
              <li key={`${headline.date}:${headline.title}`} className="text-sm text-ink">
                <span className="mr-2 text-xs text-muted tabular-nums">
                  {shortDate(headline.date)} · {headline.press}
                </span>
                {headline.title}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      <p className="m-0 flex flex-wrap gap-x-3 gap-y-1">
        {sentiment && <SourceChip provenance={provenance.sentiment} />}
        {psychology && <SourceChip provenance={psychology.provenance} />}
        {risk && <SourceChip provenance={detail.priceProvenance ?? detail.provenance} />}
      </p>
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-md bg-field px-4 py-3">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="m-0 text-lg font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

function SentimentChart({ sentiment }: { sentiment: SentimentData }) {
  return (
    <div className="h-[180px] min-w-0">
      <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1} initialDimension={{ width: 860, height: 180 }}>
        <LineChart
          data={sentiment.days.map((day) => ({ ...day, label: shortDate(day.date) }))}
          margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
        >
          <XAxis dataKey="label" tick={{ fill: CHART.muted, fontSize: 12 }} axisLine={false} tickLine={false} interval={4} />
          <YAxis
            domain={[-1, 1]}
            ticks={[-1, 0, 1]}
            tickFormatter={(value) => (value > 0 ? "긍정" : value < 0 ? "부정" : "0")}
            tick={{ fill: CHART.muted, fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={36}
          />
          <ReferenceLine y={0} stroke={CHART.line} />
          <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(value) => signed(Number(value))} />
          <Line dataKey="score" name={TERM.sentiment} stroke={CHART.priceLine} strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// 투자자별 20일 순매수 합계를 가운데 0 기준 막대로. 순매수 = 적, 순매도 = 청.
function SupplyPanel({ supply, provenance }: { supply: SupplyDemandDay[] | null; provenance: DataProvenance }) {
  if (!supply?.length) return <Unavailable>이 종목은 사고판 기록이 아직 연결되지 않았어요.</Unavailable>;
  const totals = SUPPLY_SERIES.map((series) => ({
    ...series,
    total: supply.reduce((sum, day) => sum + day[series.key], 0),
    latest: supply[supply.length - 1][series.key],
  }));
  const max = Math.max(...totals.map(({ total }) => Math.abs(total)), 1);
  const buyer = totals.reduce((top, item) => (item.total > top.total ? item : top));
  const seller = totals.reduce((low, item) => (item.total < low.total ? item : low));
  return (
    <>
      <Conclusion>
        최근 20영업일 동안 <strong className="font-semibold">{buyer.label}</strong>이 가장 많이 샀고,{" "}
        <strong className="font-semibold">{seller.label}</strong>이 가장 많이 팔았어요.
      </Conclusion>
      <ul className="m-0 flex list-none flex-col gap-3.5 p-0">
        {totals.map(({ key, label, total, latest }) => {
          const buy = total >= 0;
          const color = buy ? "var(--color-up)" : "var(--color-down)";
          return (
            <li key={key} className="grid grid-cols-[4rem_minmax(0,1fr)_auto] items-center gap-3">
              <span className="text-sm text-body">{label}</span>
              <div className="relative h-2 rounded-full bg-track" aria-hidden>
                <span className="absolute inset-y-[-4px] left-1/2 w-px bg-line" />
                <span
                  className="absolute inset-y-0 rounded-full"
                  style={{
                    [buy ? "left" : "right"]: "50%",
                    width: `${(Math.abs(total) / max) * 50}%`,
                    backgroundColor: color,
                  }}
                />
              </div>
              <span className="text-right text-sm font-semibold tabular-nums" style={{ color }}>
                {shares(total)}
                <span className="block whitespace-nowrap text-2xs font-normal text-muted">
                  {buy ? "순매수" : "순매도"} · 최근일 {shares(latest)}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
      <p className="m-0 flex flex-wrap items-center gap-x-3 text-2xs text-muted">
        <span>
          {supply[0].date} ~ {supply[supply.length - 1].date} · 순매수 수량(주) · 기타법인 제외
        </span>
        <SourceChip provenance={provenance} />
      </p>
    </>
  );
}

function FinancialPanel({ financial, provenance }: { financial: FinancialSnapshot | null; provenance: DataProvenance }) {
  if (!financial) return <Unavailable>이 종목은 재무 데이터가 아직 연결되지 않았어요.</Unavailable>;
  const value = (key: string) => financial.metrics.find((metric) => metric.key === key)?.value;
  const roe = value("roe");
  const debt = value("debt_ratio");
  return (
    <>
      {roe != null && debt != null && (
        <Conclusion>
          자기 돈 대비 1년에 <strong className="font-semibold">{Math.abs(roe)}%</strong>를 {roe < 0 ? "잃었고" : "벌었고"}, 빚은
          자기 돈의{" "}
          <strong className="font-semibold">{debt}%</strong> 수준이에요.
        </Conclusion>
      )}
      <dl className="m-0 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {financial.metrics.map((metric) => (
          <div key={metric.key} className="flex items-baseline justify-between gap-3 rounded-md bg-field px-4 py-3">
            <dt className="text-sm text-body">{FINANCIAL_TERM[metric.key] ?? metric.label}</dt>
            <dd className="m-0 flex-none text-right text-base font-semibold tabular-nums">
              {metric.value === null ? (
                <>
                  확인 불가
                  {metric.note && <span className="block text-2xs font-normal text-muted">{metric.note}</span>}
                </>
              ) : (
                <>
                  {metric.value.toLocaleString("ko-KR")}
                  {metric.unit}
                </>
              )}
            </dd>
          </div>
        ))}
      </dl>
      <details className="disclosure">
        <summary className="text-sm">계산 근거</summary>
        <ul className="m-0 mt-3 flex list-none flex-col gap-2 p-0 text-xs text-body">
          {financial.metrics.map((metric) => (
            <li key={metric.key}>
              <span className="font-medium text-ink">{metric.label}</span> = {metric.basis}
            </li>
          ))}
        </ul>
      </details>
      <p className="m-0 flex flex-wrap items-center gap-x-3 text-2xs text-muted">
        <span>{financial.period}</span>
        <SourceChip provenance={provenance} />
      </p>
    </>
  );
}

// 부호 막대: 가운데 0에서 오른쪽(적)은 오르는 쪽으로 기여, 왼쪽(청)은 내리는 쪽으로 기여.
function ContributionPanel({
  contributions,
  reasons,
  provenance,
}: {
  contributions: ContributionSignal[] | null;
  reasons: PredictionReason[];
  provenance: DataProvenance;
}) {
  if (!contributions?.length) {
    if (!reasons.length) return <Unavailable>이 예측에 연결된 근거 데이터가 없어요.</Unavailable>;
    return (
      <>
        <Conclusion>
          모델이 가장 크게 본 근거는 <strong className="font-semibold">&lsquo;{reasons[0].title}&rsquo;</strong>예요.
        </Conclusion>
        <ol className="m-0 flex list-none flex-col gap-3 p-0">
          {reasons.map((reason, index) => (
            <li key={`${reason.title}:${index}`} className="flex gap-3">
              <span className="flex-none text-sm font-semibold text-muted tabular-nums">{index + 1}</span>
              <span className="flex flex-col gap-0.5">
                <span className="text-sm text-ink">{reason.title}</span>
                <span className="text-xs text-muted">
                  {reason.detail} · {reason.sourceLabel}
                </span>
              </span>
            </li>
          ))}
        </ol>
        <SourceChip provenance={provenance} />
      </>
    );
  }
  const max = Math.max(...contributions.map(({ share }) => share), 1);
  const top = contributions[0];
  return (
    <>
      <Conclusion>
        모델이 가장 크게 본 근거는 <strong className="font-semibold">&lsquo;{top.label}&rsquo;</strong>(
        {Math.round(top.share)}%)예요.
      </Conclusion>
      <ul className="m-0 flex list-none flex-col gap-4 p-0">
        {contributions.map((signal) => {
          const up = signal.direction > 0;
          const color = up ? "var(--color-up)" : "var(--color-down)";
          return (
            <li key={signal.signal} className="flex flex-col gap-1.5">
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-medium text-ink">{signal.label}</span>
                <span className="text-xs text-muted">{CATEGORY_LABEL[signal.category]}</span>
                <span className="ml-auto flex-none text-sm font-semibold tabular-nums" style={{ color }}>
                  {up ? "▲" : "▼"} {Math.round(signal.share)}%
                </span>
              </div>
              <div className="relative h-1.5 rounded-full bg-track" aria-hidden>
                <span className="absolute inset-y-[-3px] left-1/2 w-px bg-line" />
                <span
                  className="absolute inset-y-0 rounded-full"
                  style={{
                    [up ? "left" : "right"]: "50%",
                    width: `${(signal.share / max) * 50}%`,
                    backgroundColor: color,
                  }}
                />
              </div>
              <span className="text-xs text-muted">{signal.description}</span>
            </li>
          );
        })}
      </ul>
      <p className="m-0 flex flex-wrap items-center gap-x-3 text-2xs text-muted">
        <span>▲ 오르는 쪽으로 본 근거 · ▼ 내리는 쪽으로 본 근거 · 비율 합 100%</span>
        <SourceChip provenance={provenance} />
      </p>
    </>
  );
}

// ── 계산 근거 (더 알아보기 안) ────────────────────────────────
// 개발 용어(BIT·composite·능동성 등)는 이 영역에서만 쓴다.

export function CalculationBasis({
  demo,
  detail,
  insights,
  holdings,
}: {
  demo: DemoStyleAxes;
  detail: StockDetail;
  insights: StockInsights;
  holdings: HoldingWeight[];
}) {
  const { bit, styleAxes } = demo;
  const order = bit?.cardOrder ?? DEFAULT_CARD_ORDER;
  const market = toNudgeMarket(detail, insights, holdings);
  const nudges = bit && market ? selectNudges(bit, market) : [];
  if (!bit || !styleAxes) {
    return <p className="m-0 text-sm text-muted">8축 성향 진단 결과가 없어 기본 순서로 보여 줘요.</p>;
  }
  // copy-rules:계산근거 시작
  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-start">
      <div className="flex min-w-0 flex-1 flex-col gap-2 text-sm text-body">
        <p className="m-0">
          유형: <strong className="font-semibold text-ink">{BIT_LABEL[bit.type]}</strong> · {BIAS_MODE_LABEL[bit.biasMode]}
        </p>
        <p className="m-0 tabular-nums">
          composite {signed(bit.composite)} = (능동성 {signed(bit.activeness)} + 위험감수 {signed(bit.riskTaking)}) ÷ 2 · 분류 신뢰도{" "}
          {Math.round(bit.confidence * 100)}%
        </p>
        <p className="m-0">탭 순서(카드 순서): {order.join(" → ")}</p>
        {insights.psychology && (
          <p className="m-0 tabular-nums">
            가격 흐름 분위기 psych_greed_fear_axis {signed(insights.psychology.axis)} = (fear_greed + disposition) ÷ 2 · -1
            움츠러듦 ~ +1 들뜸 (psychology_market_v1)
          </p>
        )}
        {nudges.map((nudge) => (
          <p key={nudge.id} className="m-0 tabular-nums">
            {nudge.id} 근거 축 {AXIS_META[nudge.axis].name}({nudge.axis}) {signed(nudge.ratio)} · -1{" "}
            {AXIS_META[nudge.axis].negative} ↔ +1 {AXIS_META[nudge.axis].positive}
          </p>
        ))}
        <p className="m-0 text-xs text-muted">
          Pompian 행동투자자 유형(BIT)에서 착안한 근사 분류예요. 넛지 판정 규칙: lib/profiling/nudges.ts
        </p>
      </div>
      <div className="flex-none self-center">
        <RadarChart
          width={280}
          height={220}
          data={STYLE_AXIS_IDS.map((axisId) => ({
            axis: AXIS_META[axisId].positive,
            ratio: styleAxes.axes.find(({ axis_id }) => axis_id === axisId)?.ratio ?? 0,
          }))}
          outerRadius={72}
        >
          <PolarGrid stroke={CHART.line} />
          <PolarAngleAxis dataKey="axis" tick={{ fill: CHART.muted, fontSize: 11 }} />
          <PolarRadiusAxis domain={[-1, 1]} tick={false} axisLine={false} />
          <Radar dataKey="ratio" stroke={CHART.accent} fill={CHART.accent} fillOpacity={0.25} isAnimationActive={false} />
        </RadarChart>
        <span className="block text-center text-2xs text-muted">바깥쪽 = 축의 +1 방향 · 중심 = -1</span>
      </div>
    </div>
  );
  // copy-rules:계산근거 끝
}

// 데이터 출처 전체 — 섹션마다 한 줄로 둔 출처를 한곳에 모은다.
export function SourceList({ detail, insights }: { detail: StockDetail; insights: StockInsights }) {
  const rows: [string, DataProvenance][] = [
    ["주가", detail.priceProvenance ?? detail.provenance],
    ["모델 신호·범위·근거", detail.provenance],
    [TERM.sentiment, insights.provenance.sentiment],
    [TERM.supply, insights.provenance.supply],
    [TERM.financial, insights.provenance.financial],
    [TERM.contribution, insights.provenance.contributions],
    ...(insights.psychology
      ? ([["가격 흐름으로 본 분위기", insights.psychology.provenance]] as [string, DataProvenance][])
      : []),
    ["체크포인트", combinedProvenance(detail.provenance, insights.provenance.supply, insights.provenance.sentiment)],
  ];
  return (
    <dl className="m-0 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-sm">
      {rows.map(([label, provenance]) => (
        <div key={label} className="contents">
          <dt className="text-body">{label}</dt>
          <dd className="m-0">
            <SourceChip provenance={provenance} />
          </dd>
        </div>
      ))}
      {detail.priceProvenance?.source.includes("수정주가") && (
        <p className="col-span-2 m-0 mt-1 text-xs text-muted">
          주가는 수정주가예요. 그 뒤에 있었던 배당·주식 나눔을 반영해 과거 가격을 다시 계산한 값이라, 그날 실제로 거래된
          가격과 조금 다를 수 있어요. 가격 흐름과 등락률을 비교하기에는 이 방식이 정확해요.
        </p>
      )}
    </dl>
  );
}

export function ScreenGuideBanner({ bit }: { bit: BitResult | null }) {
  if (!bit || !SCREEN_GUIDE_NOTICE.appliesTo.includes(bit.type)) return null;
  return (
    <aside role="note" className="px-1 text-xs text-muted">
      {SCREEN_GUIDE_NOTICE.text}
    </aside>
  );
}
