"use client";

// 종목 상세 인사이트 카드 6종 + 성향 요약(BIT·8축 레이더·데모 슬라이더) + 화면 안내 배너.
// 성향은 소프트 틸트다. 카드 순서와 넛지에만 쓰고 종목을 거르지 않는다.

import { Fragment, useState, type ReactNode } from "react";
import {
  CartesianGrid,
  Legend,
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
import { RISK_GRADE_META } from "@/lib/display";
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
import {
  AXIS_THRESHOLD,
  SCREEN_GUIDE_NOTICE,
  selectNudges,
  type FiredNudge,
} from "@/lib/profiling/nudges";
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
  type Period,
  type SentimentData,
  type StockInsights,
  type SupplyDemandDay,
} from "@/lib/providers";
import { CHART } from "@/lib/chart-colors";
import type { DataProvenance, StockDetail, StyleAxes, StyleAxisId } from "@/lib/types";
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

const CARD_LABEL: Record<CardId, string> = {
  nudge: "넛지",
  supply: "수급",
  sentiment: "감성",
  risk: "위험/변동성",
  contribution: "기여도 분해",
  financial: "재무",
};

// 8축 진단 결과가 없을 때의 순서
const DEFAULT_CARD_ORDER: readonly CardId[] = [
  "nudge",
  "contribution",
  "supply",
  "sentiment",
  "risk",
  "financial",
];

const WHY: Record<CardId, string> = {
  nudge:
    "설문에서 답한 성향과 지금 이 종목의 상황이 겹치는 지점을 보여 줍니다. 판단을 대신하지 않고 한 번 더 확인할 거리를 짚습니다.",
  contribution:
    "모델 신호가 어떤 근거로 구성됐는지 비율로 보여 줍니다. 한 근거에 쏠려 있는지 확인할 수 있습니다.",
  supply:
    "개인·외국인·기관이 실제로 사고판 금액의 기록입니다. 누가 어느 방향으로 거래했는지는 알 수 있지만 그 이유는 담겨 있지 않습니다.",
  sentiment:
    "관련 기사 논조가 긍정과 부정 중 어느 쪽인지 날짜별로 봅니다. 같은 사안을 다룬 기사가 많으면 점수가 한쪽으로 몰릴 수 있습니다.",
  risk:
    "가격이 얼마나 크게 흔들렸고 최근 고점에서 얼마나 떨어져 있는지 봅니다. 손실을 견딜 수 있는 정도와 나란히 놓고 보는 지표입니다.",
  financial:
    "회사가 이익을 내는 힘과 재무 구조를 봅니다. 가격 움직임과 별개로 회사의 기초 체력을 확인하는 용도입니다.",
};

const CATEGORY_META: Record<
  ContributionCategory,
  { label: string; bar: string; bg: string; text: string }
> = {
  technical: { label: "기술적", bar: CHART.brand, bg: CHART.brandSoft, text: CHART.brand },
  financial: { label: "재무", bar: CHART.cat2, bg: CHART.cat2Tint, text: CHART.cat2 },
  sentiment: { label: "감성", bar: CHART.cat3, bg: CHART.cat3Tint, text: CHART.cat3 },
  supply: { label: "수급", bar: CHART.cat4, bg: CHART.sigNgTint, text: CHART.sigNg },
};

const SUPPLY_SERIES = [
  { key: "retail", label: "개인", color: CHART.sigNg },
  { key: "foreign", label: "외국인", color: CHART.brand },
  { key: "institution", label: "기관", color: CHART.cat2 },
  { key: "otherCorp", label: "기타법인", color: CHART.cat3 },
] as const;

const TOOLTIP_STYLE = { border: `1px solid ${CHART.line}`, borderRadius: 6, fontSize: 11 };

const signed = (value: number, digits = 2) => `${value > 0 ? "+" : ""}${value.toFixed(digits)}`;
const signedPercent = (ratio: number) => `${ratio > 0 ? "+" : ""}${(ratio * 100).toFixed(1)}%`;
const eok = (value: number) => `${value > 0 ? "+" : ""}${value.toLocaleString("ko-KR")}억`;
const shortDate = (iso: string) => iso.slice(5).replace("-", ".");

export type DemoStyleAxes = ReturnType<typeof useDemoStyleAxes>;

// "다른 성향으로 보기": BIT 4유형 프리셋으로 이 화면만 바꿔 본다. DB·localStorage에 쓰지 않는다.
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

function WhyTooltip({ id, text }: { id: string; text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        aria-label="이 지표를 왜 봐야 하나"
        aria-describedby={open ? id : undefined}
        onClick={() => setOpen(true)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(event) => event.key === "Escape" && setOpen(false)}
        className="grid size-[18px] place-items-center rounded-full border border-edge bg-white text-2xs font-medium text-muted hover:border-brand hover:text-brand"
      >
        ?
      </button>
      {open && (
        <span
          role="tooltip"
          id={id}
          className="absolute left-0 top-6 z-20 w-[min(300px,80vw)] rounded-lg border border-line bg-white px-3 py-2.5 text-xs font-normal leading-5 text-body shadow-modal"
        >
          <strong className="mb-0.5 block text-ink">이 지표를 왜 봐야 하나</strong>
          {text}
        </span>
      )}
    </span>
  );
}

function InsightCard({
  id,
  title,
  note,
  provenance,
  emphasized = false,
  children,
}: {
  id: CardId;
  title: string;
  note?: string;
  provenance: DataProvenance;
  emphasized?: boolean;
  children: ReactNode;
}) {
  const border = emphasized ? "border border-edge shadow-hairline" : "border border-line";
  return (
    <section
      data-card={id}
      aria-labelledby={`insight-${id}`}
      className={`flex flex-col gap-3.5 rounded-lg bg-white px-7 py-[22px] ${border}`}
    >
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <h2 id={`insight-${id}`} className="text-base font-semibold">
          {title}
        </h2>
        <WhyTooltip id={`why-${id}`} text={WHY[id]} />
        {note && <span className="text-xs text-faint">{note}</span>}
        <span className="ml-auto">
          <SourceChip provenance={provenance} />
        </span>
      </div>
      {children}
    </section>
  );
}

function Unavailable({ children }: { children: ReactNode }) {
  return (
    <p className="m-0 rounded-lg border border-dashed border-edge bg-field px-4 py-5 text-center text-sm leading-6 text-muted">
      {children}
    </p>
  );
}

function NudgeContent({
  bit,
  hasMarket,
  nudges,
}: {
  bit: BitResult | null;
  hasMarket: boolean;
  nudges: FiredNudge[];
}) {
  if (!bit) return <Unavailable>8축 성향 진단 결과가 없어 넛지를 판정하지 않습니다.</Unavailable>;
  if (!hasMarket) {
    return <Unavailable>이 종목은 넛지 판정에 필요한 시장 데이터가 아직 연결되지 않았습니다.</Unavailable>;
  }
  if (!nudges.length) {
    return <Unavailable>지금 이 종목에서 답하신 성향과 겹치는 확인 거리가 없습니다.</Unavailable>;
  }
  return (
    <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
      {nudges.map((nudge) => {
        const meta = AXIS_META[nudge.axis];
        const threshold =
          nudge.ratio >= 0 ? `≥ +${AXIS_THRESHOLD.toFixed(2)}` : `≤ -${AXIS_THRESHOLD.toFixed(2)}`;
        return (
          <li
            key={nudge.id}
            data-nudge={nudge.id}
            className="rounded-md bg-field px-4 py-3.5"
          >
            <p className="m-0 text-base leading-relaxed text-ink">{nudge.text}</p>
            <p className="m-0 mt-2 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-muted">
              <span className="rounded-md bg-white px-2 py-0.5 font-medium text-brand">{nudge.id}</span>
              <span>
                근거 축 <strong className="text-body">{meta.name}</strong> ({nudge.axis})
              </span>
              <span className="tabular-nums">
                응답값 <strong className="text-body">{signed(nudge.ratio)}</strong> · 발화 기준{" "}
                {threshold}
              </span>
              <span>
                -1 {meta.negative} ↔ +1 {meta.positive}
              </span>
              {nudge.id === "N08" && (
                <span className="font-medium text-body">보유 비중: 매입금액(수량 × 평단) 기준</span>
              )}
            </p>
          </li>
        );
      })}
    </ul>
  );
}

function ContributionContent({ contributions }: { contributions: ContributionSignal[] }) {
  return (
    <div className="flex flex-col gap-3.5">
      {contributions.map((signal) => {
        const meta = CATEGORY_META[signal.category];
        return (
          <div key={signal.signal} className="flex flex-col gap-1.5">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span
                className="inline-flex h-[22px] items-center rounded-md px-2 text-xs font-medium"
                style={{ backgroundColor: meta.bg, color: meta.text }}
              >
                {meta.label}
              </span>
              <span className="font-medium text-ink">{signal.label}</span>
              <span className="ml-auto font-semibold tabular-nums">
                {Math.round(signal.share)}%
              </span>
            </div>
            <div className="h-2 rounded bg-track">
              <div
                className="h-2 rounded"
                style={{ width: `${signal.share}%`, backgroundColor: meta.bar }}
              />
            </div>
            <span className="text-xs text-faint">{signal.description}</span>
          </div>
        );
      })}
    </div>
  );
}

function SupplyContent({ supply }: { supply: SupplyDemandDay[] }) {
  const latest = supply[supply.length - 1];
  return (
    <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {SUPPLY_SERIES.map((series) => (
          <div key={series.key} className="rounded-lg bg-field px-4 py-3">
            <span className="text-xs font-medium" style={{ color: series.color }}>
              {series.label}
            </span>
            <div className="mt-1 text-lg font-semibold tabular-nums">
              {eok(supply.reduce((sum, day) => sum + day[series.key], 0))}
            </div>
            <span className="text-xs text-faint tabular-nums">
              20일 합계 · 최근일 {eok(latest[series.key])}
            </span>
          </div>
        ))}
      </div>
      <div className="h-[220px] min-w-0">
        <ResponsiveContainer
          width="100%"
          height="100%"
          minWidth={1}
          minHeight={1}
          initialDimension={{ width: 960, height: 220 }}
        >
          <LineChart
            data={supply.map((day) => ({ ...day, label: shortDate(day.date) }))}
            margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
          >
            <CartesianGrid stroke={CHART.track} vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: CHART.muted, fontSize: 10 }}
              axisLine={{ stroke: CHART.edge }}
              tickLine={false}
              interval={3}
            />
            <YAxis
              tick={{ fill: CHART.faint, fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              width={56}
              tickFormatter={(value) => `${Number(value).toLocaleString("ko-KR")}억`}
            />
            <ReferenceLine y={0} stroke={CHART.edge} />
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(value) => eok(Number(value))} />
            <Legend iconType="plainline" wrapperStyle={{ fontSize: 11 }} />
            {SUPPLY_SERIES.map((series) => (
              <Line
                key={series.key}
                dataKey={series.key}
                name={series.label}
                stroke={series.color}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="m-0 text-xs text-faint">
        순매수(+)·순매도(-) 금액의 일별 기록입니다. 거래 주체가 왜 거래했는지는 담겨 있지 않습니다.
      </p>
    </>
  );
}

function SentimentContent({
  sentiment,
  periodMismatch,
}: {
  sentiment: SentimentData;
  periodMismatch: boolean;
}) {
  const { days, headlines } = sentiment;
  const latest = days[days.length - 1];
  const previous = days[days.length - 2];
  return (
    <>
      {periodMismatch && (
        <p
          data-period-mismatch
          className="m-0 rounded-lg border border-warn-line bg-warn-tint px-3.5 py-2 text-xs font-semibold text-warn"
        >
          현재 시세 데이터와 기간이 다릅니다. 실데이터 연동 시 정합됩니다.
        </p>
      )}
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-body tabular-nums">
        <span>
          최근일 감성 <strong className="text-ink">{signed(latest.score)}</strong>
        </span>
        {previous && <span>전일 대비 {signed(latest.score - previous.score)}</span>}
        <span>기사 {latest.articleCount}건</span>
      </div>
      <div className="h-[200px] min-w-0">
        <ResponsiveContainer
          width="100%"
          height="100%"
          minWidth={1}
          minHeight={1}
          initialDimension={{ width: 960, height: 200 }}
        >
          <LineChart
            data={days.map((day) => ({ ...day, label: shortDate(day.date) }))}
            margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
          >
            <CartesianGrid stroke={CHART.track} vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: CHART.muted, fontSize: 10 }}
              axisLine={{ stroke: CHART.edge }}
              tickLine={false}
              interval={3}
            />
            <YAxis
              domain={[-1, 1]}
              ticks={[-1, -0.5, 0, 0.5, 1]}
              tick={{ fill: CHART.faint, fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              width={34}
            />
            <ReferenceLine y={0} stroke={CHART.edge} />
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(value) => signed(Number(value))} />
            <Line
              dataKey="score"
              name="감성 점수"
              stroke={CHART.cat3}
              strokeWidth={2}
              dot={{ r: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-col gap-2">
        <span className="text-xs font-medium text-muted">대표 기사 3건 · 최근일 감성 강도 순</span>
        <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
          {headlines.map((headline) => (
            <li
              key={`${headline.date}:${headline.title}`}
              className="flex flex-wrap gap-x-2 rounded-lg bg-field px-3.5 py-2.5 text-sm"
            >
              <span className="text-xs text-faint tabular-nums">
                {shortDate(headline.date)} · {headline.press}
              </span>
              <span className="text-ink">{headline.title}</span>
            </li>
          ))}
        </ul>
      </div>
      <p className="m-0 text-xs text-faint">점수 -1(부정) ~ +1(긍정)</p>
    </>
  );
}

function RiskContent({ detail }: { detail: StockDetail }) {
  const risk = riskSnapshot(detail);
  if (!risk) return <Unavailable>이 종목은 변동성 계산에 필요한 가격 데이터가 없습니다.</Unavailable>;
  const grade = RISK_GRADE_META[risk.riskGrade];
  const volatilityTop = Math.max(1, Math.round((1 - risk.volatilityPercentile) * 100));
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
      <div className="flex flex-col gap-1 rounded-lg bg-field px-4 py-3.5">
        <span className="text-xs text-muted">변동성 (연환산)</span>
        <span className="text-xl font-semibold tabular-nums">
          {(risk.volatilityAnnual * 100).toFixed(1)}%
        </span>
        <span className="text-xs text-faint">최근 60거래일 · 시장 상위 {volatilityTop}%</span>
      </div>
      <div className="flex flex-col gap-1.5 rounded-lg bg-field px-4 py-3.5">
        <span className="text-xs text-muted">위험등급</span>
        <span
          className={`text-xl font-semibold tabular-nums ${
            grade.tone === "warn" ? "text-warn" : ""
          }`}
        >
          {risk.riskGrade}등급 · {grade.label}
        </span>
        <span className="text-xs text-faint">숫자가 클수록 안전합니다 (1 매우 위험 ~ 5 매우 안전)</span>
      </div>
      <div className="flex flex-col gap-1 rounded-lg bg-field px-4 py-3.5">
        <span className="text-xs text-muted">3개월 고점 대비</span>
        <span className="text-xl font-semibold tabular-nums">
          {signedPercent(risk.drawdownFrom3mHigh)}
        </span>
        <span className="text-xs text-faint tabular-nums">
          최근 3거래일 {signedPercent(risk.return3d)}
        </span>
      </div>
    </div>
  );
}

function FinancialContent({ financial }: { financial: FinancialSnapshot }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
      {financial.metrics.map((metric) => (
        <div key={metric.key} className="flex flex-col gap-1 rounded-lg bg-field px-4 py-3">
          <span className="text-xs text-muted">{metric.label}</span>
          <span className="text-lg font-semibold tabular-nums">
            {metric.value.toLocaleString("ko-KR")}
            {metric.unit}
          </span>
          <span className="text-xs leading-4 text-faint">{metric.description}</span>
        </div>
      ))}
    </div>
  );
}

function StyleProfilePanel({ demo, order }: { demo: DemoStyleAxes; order: readonly CardId[] }) {
  const { bit, styleAxes } = demo;

  return (
    <section
      aria-labelledby="style-profile-title"
      className="flex flex-col gap-4 rounded-lg border border-line bg-white px-7 py-[22px]"
    >
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <h2 id="style-profile-title" className="text-base font-semibold">
          투자 성향 요약
        </h2>
        {demo.viewAs && (
          <span className="inline-flex h-[22px] items-center rounded-md border border-warn-line bg-warn-tint px-2 text-xs font-medium text-warn">
            {BIT_LABEL[demo.viewAs]}의 시선으로 보는 중 · 내 결과 아님
          </span>
        )}
      </div>

      {!styleAxes || !bit ? (
        <Unavailable>8축 성향 진단 결과가 없어 카드를 기본 순서로 표시합니다.</Unavailable>
      ) : (
        <div className="flex flex-col gap-4 md:flex-row md:items-center">
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            <span data-bit-type={bit.lowConfidence ? "low_confidence" : bit.type} className="text-lg font-semibold text-ink">
              {bit.lowConfidence
                ? "아직 판단하기에 응답이 부족합니다"
                : `${BIT_LABEL[bit.type]} · ${BIAS_MODE_LABEL[bit.biasMode]}`}
            </span>
            <span className="text-xs text-body tabular-nums">
              종합 {signed(bit.composite)} = (능동성 {signed(bit.activeness)} + 위험감수{" "}
              {signed(bit.riskTaking)}) ÷ 2 · 분류 신뢰도 {Math.round(bit.confidence * 100)}%
            </span>
            <span className="text-xs leading-5 text-faint">
              Pompian 행동투자자 유형(BIT)에서 착안한 근사 분류입니다. 카드 순서와 넛지에만 쓰고
              종목을 거르지 않습니다.
            </span>
            <span data-card-order={order.join(",")} className="text-xs text-muted">
              카드 순서: {order.map((id) => CARD_LABEL[id]).join(" → ")}
            </span>
          </div>
          <div className="flex-none self-center">
            <RadarChart
              width={300}
              height={230}
              data={STYLE_AXIS_IDS.map((axisId) => ({
                axis: AXIS_META[axisId].positive,
                ratio: styleAxes.axes.find(({ axis_id }) => axis_id === axisId)?.ratio ?? 0,
              }))}
              outerRadius={78}
            >
              <PolarGrid stroke={CHART.line} />
              <PolarAngleAxis dataKey="axis" tick={{ fill: CHART.muted, fontSize: 10 }} />
              <PolarRadiusAxis domain={[-1, 1]} tick={false} axisLine={false} />
              <Radar
                dataKey="ratio"
                stroke={CHART.brand}
                fill={CHART.brand}
                fillOpacity={0.18}
                isAnimationActive={false}
              />
            </RadarChart>
            <span className="block text-center text-2xs text-faint">
              바깥쪽 = 축의 +1 방향 · 중심 = -1
            </span>
          </div>
        </div>
      )}

      {styleAxes && (
        <div className="flex flex-col gap-2.5 border-t border-line-soft pt-3">
          <span className="text-sm font-medium text-ink">다른 성향으로 보기</span>
          <p className="m-0 text-xs text-muted">
            같은 종목을 다른 유형은 어떤 순서와 주의 안내로 보게 되는지 바꿔 볼 수 있어요. 이 화면에서만
            바뀌고 내 설문 결과는 그대로예요.
          </p>
          <div role="group" aria-label="다른 성향으로 보기" className="flex flex-wrap gap-2">
            {[null, ...BIT_TYPES].map((type) => {
              const active = demo.viewAs === type;
              return (
                <button
                  key={type ?? "mine"}
                  type="button"
                  aria-pressed={active}
                  onClick={() => demo.setViewAs(type)}
                  className={`h-9 rounded-lg border px-3.5 text-xs font-medium ${
                    active
                      ? "border-brand bg-brand-soft text-brand-deep"
                      : "border-edge bg-white text-body hover:border-brand"
                  }`}
                >
                  {type ? BIT_LABEL[type] : "내 성향"}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

export default function InsightSection({
  detail,
  insights,
  holdings,
  demo,
}: {
  detail: StockDetail;
  insights: StockInsights;
  holdings: HoldingWeight[];
  demo: DemoStyleAxes;
}) {
  const market = toNudgeMarket(detail, insights, holdings);
  const nudges = demo.bit && market ? selectNudges(demo.bit, market) : [];
  const order = demo.bit?.cardOrder ?? DEFAULT_CARD_ORDER;
  const { supply, sentiment, contributions, financial, provenance } = insights;
  const prices: Period | null = pricePeriod(detail);
  const sentimentDates = sentiment ? sentimentPeriod(sentiment) : null;
  // 기간 라벨은 "<데이터> 데이터: 시작 ~ 끝" 한 형식으로 쓴다. 실데이터 여부는 카드의 SourceChip이 맡는다.
  const sentimentNote = sentimentDates
    ? `감성 데이터: ${sentimentDates.start} ~ ${sentimentDates.end}`
    : "일별 감성 점수 · 대표 기사 3건";
  const priceNote = prices
    ? `시세 데이터: ${prices.start} ~ ${prices.end}`
    : "최근 60거래일 가격 기준";
  const supplyNote = supply?.length
    ? `수급 데이터: ${supply[0].date} ~ ${supply[supply.length - 1].date} · 순매수 억원`
    : "개인·외국인·기관·기타법인 최근 20영업일 순매수 · 억원";
  const periodMismatch = Boolean(prices && sentimentDates && !periodsOverlap(prices, sentimentDates));

  const cards: Record<CardId, ReactNode> = {
    nudge: (
      <InsightCard
        id="nudge"
        title="확인해 볼 점"
        note="답하신 성향과 이 종목 상황이 겹치는 지점 · 최대 2개"
        provenance={combinedProvenance(detail.provenance, provenance.supply, provenance.sentiment)}
        emphasized
      >
        <NudgeContent bit={demo.bit} hasMarket={Boolean(market)} nudges={nudges} />
      </InsightCard>
    ),
    contribution: (
      <InsightCard
        id="contribution"
        title="기여도 분해"
        note="모델 신호의 근거 구성 · 합 100%"
        provenance={provenance.contributions}
      >
        {contributions?.length ? (
          <ContributionContent contributions={contributions} />
        ) : (
          <Unavailable>이 종목은 신호 기여도 데이터가 아직 연결되지 않았습니다.</Unavailable>
        )}
      </InsightCard>
    ),
    supply: (
      <InsightCard id="supply" title="수급" note={supplyNote} provenance={provenance.supply}>
        {supply?.length ? (
          <SupplyContent supply={supply} />
        ) : (
          <Unavailable>이 종목은 수급 데이터가 아직 연결되지 않았습니다.</Unavailable>
        )}
      </InsightCard>
    ),
    sentiment: (
      <InsightCard id="sentiment" title="뉴스 감성" note={sentimentNote} provenance={provenance.sentiment}>
        {sentiment?.days.length ? (
          <SentimentContent sentiment={sentiment} periodMismatch={periodMismatch} />
        ) : (
          <Unavailable>이 종목은 뉴스 감성 데이터가 아직 연결되지 않았습니다.</Unavailable>
        )}
      </InsightCard>
    ),
    risk: (
      <InsightCard id="risk" title="위험/변동성" note={priceNote} provenance={detail.provenance}>
        <RiskContent detail={detail} />
      </InsightCard>
    ),
    financial: (
      <InsightCard id="financial" title="재무" note={financial?.period} provenance={provenance.financial}>
        {financial ? (
          <FinancialContent financial={financial} />
        ) : (
          <Unavailable>이 종목은 재무 데이터가 아직 연결되지 않았습니다.</Unavailable>
        )}
      </InsightCard>
    ),
  };

  return (
    <>
      <StyleProfilePanel demo={demo} order={order} />
      {order.map((id) => (
        <Fragment key={id}>{cards[id]}</Fragment>
      ))}
    </>
  );
}

export function ScreenGuideBanner({ bit }: { bit: BitResult | null }) {
  if (!bit || !SCREEN_GUIDE_NOTICE.appliesTo.includes(bit.type)) return null;
  return (
    <aside
      role="note"
      className="flex items-center gap-3 rounded-md bg-field px-4 py-3 text-sm text-body"
    >
      <span className="grid size-[18px] flex-none place-items-center rounded-full border border-edge bg-white text-2xs text-muted">
        ?
      </span>
      {SCREEN_GUIDE_NOTICE.text}
    </aside>
  );
}
