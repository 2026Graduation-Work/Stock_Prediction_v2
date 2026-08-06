"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import DisclaimerFooter from "./disclaimer-footer";
import SiteHeader from "./site-header";
import {
  METRICS,
  ML_METRICS,
  PROFILE_LABEL,
  TRADING_METRICS,
  deltaOutcome,
  formatDeltaValue,
  formatMetricValue,
  type DeltaOutcome,
  type MetricDefinition,
} from "@/lib/performance-display";
import type {
  ComparisonDeltaRow,
  ComparisonMetricRow,
  ComparisonProfile,
  ComparisonResults,
  ComparisonSample,
} from "@/lib/performance-types";
import type { InvestorProfileSummary, MarketStatus } from "@/lib/types";

interface PerformanceDashboardProps {
  data: ComparisonResults;
  isSample: boolean;
  conclusion: string;
  profile: InvestorProfileSummary;
  marketStatus: MarketStatus;
}

const CONTROL_CONDITIONS = [
  "동일 유니버스",
  "동일 기간",
  "동일 시드",
  "공용 평가함수",
];

const OUTCOME_STYLE: Record<DeltaOutcome, { text: string; cell: string; label: string }> = {
  improved: {
    text: "text-[#1e7d4f]",
    cell: "bg-[#eef6f1]",
    label: "개선",
  },
  worsened: {
    text: "text-[#b03a34]",
    cell: "bg-[#fbe9e8]",
    label: "저하",
  },
  unchanged: {
    text: "text-muted",
    cell: "bg-field",
    label: "동일",
  },
  neutral: {
    text: "text-body",
    cell: "bg-field",
    label: "증감",
  },
  unavailable: {
    text: "text-faint",
    cell: "bg-field",
    label: "미산출",
  },
};

const CHART_SERIES = [
  { key: "stableA", label: "안정형 A", fill: "#98a2b3" },
  { key: "stableB", label: "안정형 B", fill: "#2f5fd0" },
  { key: "aggressiveA", label: "공격형 A", fill: "#c58a52" },
  { key: "aggressiveB", label: "공격형 B", fill: "#1e7d4f" },
] as const;

export default function PerformanceDashboard({
  data,
  isSample,
  conclusion,
  profile,
  marketStatus,
}: PerformanceDashboardProps) {
  return (
    <div className="min-h-screen w-full">
      <SiteHeader
        profile={profile}
        marketStatus={marketStatus}
        activePage="performance"
        sectionLabel="모델 성능 비교"
      />

      <section className="border-b border-line bg-white">
        <div className="mx-auto box-border w-full max-w-[1440px] px-6 py-6 lg:px-8">
          <div className="flex flex-wrap items-center gap-2.5">
            {isSample && (
              <span className="rounded-md border border-[#e6c96b] bg-[#fff8df] px-2.5 py-1 text-[11px] font-extrabold text-[#8a6500]">
                샘플 데이터
              </span>
            )}
            <span className="text-xs font-semibold text-muted">연구 질문</span>
          </div>
          <h1 className="mt-2 text-[26px] font-extrabold leading-tight">
            심리 지수를 반영하면 예측이 나아지는가?
          </h1>
          <p className="mt-2 max-w-[920px] text-sm leading-6 text-body">
            Baseline(A)은 차트 피처만, Treatment(B)는 같은 피처에 합성 심리지수와 뉴스
            감성을 추가합니다. 두 모델 사이에서 바뀌는 조건은 피처 세트뿐입니다.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {CONTROL_CONDITIONS.map((condition) => (
              <span
                key={condition}
                className="rounded-md border border-edge bg-field px-2.5 py-1.5 text-xs font-bold text-body"
              >
                {condition}
              </span>
            ))}
          </div>
        </div>
      </section>

      <main className="mx-auto box-border flex w-full max-w-[1440px] flex-col gap-8 px-6 py-7 lg:px-8">
        <section aria-labelledby="four-run-title">
          <SectionHeading
            id="four-run-title"
            title="4런 전체 구간 비교"
            description="안정형·공격형 각각 A/B를 같은 표본에서 평가"
          />
          <div className="mt-3 overflow-x-auto rounded-lg border border-line bg-white">
            <FourRunTable
              rows={data.four_run_metrics}
              deltas={data.comparison_deltas.filter(({ sample }) => sample === "all")}
            />
          </div>
          <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 px-1 text-[11px] text-faint">
            <span>AUC·적중률·Sharpe·MDD·누적수익률: 값이 클수록 우수</span>
            <span>Brier·ECE: 값이 작을수록 우수</span>
            <span>거래 수: 우열 없이 규모만 비교</span>
          </div>
        </section>

        <section aria-labelledby="subsample-title">
          <SectionHeading
            id="subsample-title"
            title="급변 구간 서브샘플"
            description="변동성 상위 20% 날짜를 분리해 심리 피처 효과를 재평가"
            marker="핵심 분석"
          />
          <div className="mt-3 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <SamplePanel
              title="전체 구간에서의 A vs B"
              subtitle="테스트 기간의 모든 관측치"
              sample="all"
              rows={data.four_run_metrics}
              deltas={data.comparison_deltas}
            />
            <SamplePanel
              title="급변 구간에서의 A vs B"
              subtitle="일별 시장 변동성 상위 20%"
              sample="volatile_top_20pct"
              rows={data.volatile_subsample_metrics}
              deltas={data.comparison_deltas}
            />
          </div>
        </section>

        <section
          aria-labelledby="conclusion-title"
          className="border-l-4 border-brand bg-white px-5 py-5"
        >
          <div className="flex flex-wrap items-center gap-2.5">
            <h2 id="conclusion-title" className="text-base font-extrabold">
              연구 결론
            </h2>
            <span className="rounded-md bg-track px-2 py-1 text-[10.5px] font-bold text-muted">
              {isSample ? "실제 결과 반영 전" : "러너 결과 반영"}
            </span>
          </div>
          <p className="mt-2 text-sm leading-6 text-body">{conclusion}</p>
        </section>
      </main>

      <DisclaimerFooter fixed={false} />
    </div>
  );
}

function SectionHeading({
  id,
  title,
  description,
  marker,
}: {
  id: string;
  title: string;
  description: string;
  marker?: string;
}) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1 px-0.5">
      {marker && (
        <span className="rounded-md bg-brand-soft px-2 py-1 text-[10.5px] font-extrabold text-brand">
          {marker}
        </span>
      )}
      <h2 id={id} className="text-lg font-extrabold">
        {title}
      </h2>
      <span className="text-xs text-faint">{description}</span>
    </div>
  );
}

function FourRunTable({
  rows,
  deltas,
}: {
  rows: ComparisonMetricRow[];
  deltas: ComparisonDeltaRow[];
}) {
  return (
    <table className="min-w-[940px] w-full table-fixed border-collapse text-left">
      <thead>
        <tr className="border-b border-line bg-field text-[11px] font-bold text-muted">
          <th rowSpan={2} className="w-[160px] border-r border-line px-4 py-3">
            실험 런
          </th>
          <th colSpan={ML_METRICS.length} className="border-r border-line px-3 py-2 text-center">
            ML 지표
          </th>
          <th colSpan={TRADING_METRICS.length} className="px-3 py-2 text-center">
            Trading 지표
          </th>
        </tr>
        <tr className="border-b border-line bg-field text-[11px] font-bold text-body">
          {METRICS.map((metric, index) => (
            <th
              key={metric.key}
              className={`px-2 py-2.5 text-right ${
                index === ML_METRICS.length - 1 ? "border-r border-line" : ""
              }`}
            >
              {metric.label}
              <span className="ml-1 text-[10px] text-faint">
                {metric.direction === "higher"
                  ? "↑"
                  : metric.direction === "lower"
                    ? "↓"
                    : "·"}
              </span>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, rowIndex) => {
          const delta = deltas.find(({ profile }) => profile === row.profile);
          const startsProfile = rowIndex > 0 && rows[rowIndex - 1]?.profile !== row.profile;
          return (
            <tr
              key={`${row.profile}-${row.variant}`}
              className={`${startsProfile ? "border-t-2 border-edge" : "border-t border-line-soft"}`}
            >
              <th className="border-r border-line px-4 py-3.5">
                <div className="flex items-center gap-2">
                  <span className="font-extrabold">{PROFILE_LABEL[row.profile]}</span>
                  <span
                    className={`grid size-6 place-items-center rounded-md text-[11px] font-extrabold ${
                      row.variant === "B"
                        ? "bg-brand text-white"
                        : "border border-edge bg-field text-body"
                    }`}
                  >
                    {row.variant}
                  </span>
                </div>
                <div className="mt-1 text-[10.5px] font-medium text-faint">
                  {row.feature_set === "baseline" ? "차트 피처" : "차트 + 심리 피처"} · {row.feature_count}개
                </div>
              </th>
              {METRICS.map((metric, index) => {
                const deltaValue = delta?.[metric.deltaKey] ?? null;
                const outcome = row.variant === "B" ? deltaOutcome(deltaValue, metric) : null;
                return (
                  <td
                    key={metric.key}
                    className={`px-2 py-3 text-right tabular-nums ${
                      index === ML_METRICS.length - 1 ? "border-r border-line" : ""
                    } ${outcome ? OUTCOME_STYLE[outcome].cell : ""}`}
                  >
                    <div className="text-[13px] font-bold text-ink">
                      {formatMetricValue(row[metric.key], metric)}
                    </div>
                    {row.variant === "B" && (
                      <div className={`mt-0.5 text-[10.5px] font-bold ${OUTCOME_STYLE[outcome!].text}`}>
                        Δ {formatDeltaValue(deltaValue, metric)} · {OUTCOME_STYLE[outcome!].label}
                      </div>
                    )}
                  </td>
                );
              })}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function SamplePanel({
  title,
  subtitle,
  sample,
  rows,
  deltas,
}: {
  title: string;
  subtitle: string;
  sample: ComparisonSample;
  rows: ComparisonMetricRow[];
  deltas: ComparisonDeltaRow[];
}) {
  const chartData = ML_METRICS.map((metric) => ({
    metric: metric.shortLabel,
    stableA: metricValue(rows, "stable", "A", metric),
    stableB: metricValue(rows, "stable", "B", metric),
    aggressiveA: metricValue(rows, "aggressive", "A", metric),
    aggressiveB: metricValue(rows, "aggressive", "B", metric),
  }));

  return (
    <article className="min-w-0 rounded-lg border border-line bg-white">
      <div className="border-b border-line px-4 py-3.5">
        <h3 className="text-sm font-extrabold">{title}</h3>
        <p className="mt-0.5 text-[11px] text-faint">{subtitle}</p>
      </div>

      <div className="px-3 pb-1 pt-3">
        <div className="flex items-center justify-between px-1">
          <span className="text-[11px] font-bold text-muted">ML 지표 절대값</span>
          <span className="text-[10px] text-faint">y축 0~1 고정</span>
        </div>
        <div className="mt-1 h-[230px] min-w-0">
          <ResponsiveContainer
            width="100%"
            height="100%"
            minWidth={1}
            minHeight={1}
            initialDimension={{ width: 560, height: 230 }}
          >
            <BarChart data={chartData} margin={{ top: 10, right: 4, left: -18, bottom: 0 }}>
              <CartesianGrid stroke="#eef1f5" vertical={false} />
              <XAxis
                dataKey="metric"
                tick={{ fill: "#667085", fontSize: 10 }}
                axisLine={{ stroke: "#d5dae3" }}
                tickLine={false}
              />
              <YAxis
                domain={[0, 1]}
                ticks={[0, 0.25, 0.5, 0.75, 1]}
                tick={{ fill: "#98a2b3", fontSize: 9 }}
                axisLine={false}
                tickLine={false}
                width={34}
              />
              <Tooltip
                cursor={{ fill: "#f4f5f7" }}
                contentStyle={{
                  border: "1px solid #e4e7ec",
                  borderRadius: 6,
                  fontSize: 11,
                }}
                formatter={(value) => Number(value).toFixed(3)}
              />
              <Legend iconType="square" iconSize={8} wrapperStyle={{ fontSize: 10 }} />
              {CHART_SERIES.map((series) => (
                <Bar
                  key={series.key}
                  dataKey={series.key}
                  name={series.label}
                  fill={series.fill}
                  maxBarSize={18}
                  isAnimationActive={false}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="overflow-x-auto border-t border-line">
        <table className="w-full min-w-[440px] table-fixed border-collapse">
          <thead>
            <tr className="bg-field text-[10.5px] font-bold text-muted">
              <th className="w-[92px] px-3 py-2 text-left">지표</th>
              <th className="px-2 py-2 text-left">안정형 A → B</th>
              <th className="px-2 py-2 text-left">공격형 A → B</th>
            </tr>
          </thead>
          <tbody>
            {METRICS.map((metric) => (
              <tr key={metric.key} className="border-t border-line-soft">
                <th className="px-3 py-2 text-left text-[10.5px] font-bold text-body">
                  {metric.shortLabel}
                </th>
                {(["stable", "aggressive"] as const).map((comparisonProfile) => (
                  <PairCell
                    key={comparisonProfile}
                    metric={metric}
                    profile={comparisonProfile}
                    sample={sample}
                    rows={rows}
                    deltas={deltas}
                  />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
}

function PairCell({
  metric,
  profile,
  sample,
  rows,
  deltas,
}: {
  metric: MetricDefinition;
  profile: ComparisonProfile;
  sample: ComparisonSample;
  rows: ComparisonMetricRow[];
  deltas: ComparisonDeltaRow[];
}) {
  const baseline = findMetricRow(rows, profile, "A");
  const treatment = findMetricRow(rows, profile, "B");
  const delta = deltas.find((row) => row.profile === profile && row.sample === sample);
  const deltaValue = baseline && treatment ? (delta?.[metric.deltaKey] ?? null) : null;
  const outcome = deltaOutcome(deltaValue, metric);
  const style = OUTCOME_STYLE[outcome];
  const baselineValue = baseline?.[metric.key] ?? null;
  const treatmentValue = treatment?.[metric.key] ?? null;

  return (
    <td className="px-2 py-2 tabular-nums">
      <div className="whitespace-nowrap text-[10.5px] font-semibold text-body">
        A {formatMetricValue(baselineValue, metric)} → B{" "}
        {formatMetricValue(treatmentValue, metric)}
      </div>
      <div className={`mt-0.5 text-[10px] font-extrabold ${style.text}`}>
        Δ {formatDeltaValue(deltaValue, metric)} · {style.label}
      </div>
    </td>
  );
}

function metricValue(
  rows: ComparisonMetricRow[],
  profile: ComparisonProfile,
  variant: "A" | "B",
  metric: MetricDefinition,
): number | null {
  return findMetricRow(rows, profile, variant)?.[metric.key] ?? null;
}

function findMetricRow(
  rows: ComparisonMetricRow[],
  profile: ComparisonProfile,
  variant: "A" | "B",
): ComparisonMetricRow | undefined {
  return rows.find((candidate) => candidate.profile === profile && candidate.variant === variant);
}
