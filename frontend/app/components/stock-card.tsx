import Link from "next/link";
import {
  AGREEMENT_LABEL,
  HORIZON_META,
  RISK_FLAG_LABEL,
  RISK_GRADE_META,
  SIGNAL_META,
  SIGNAL_ORDER,
} from "@/lib/display";
import type { RecommendedStock } from "@/lib/types";
import SourceChip from "./source-chip";

// 수익률 밴드 바: 0%가 바 중앙(50%), 수익률 1%p당 5% 이동
const BAND_SCALE = 5;

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function formatPercent(value: number) {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

// 5단계 중 현재 위치를 보여주는 막대. 활성 구간만 신호색, 나머지는 회색.
// 점+글로우 대신 세그먼트 — 작은 크기에서 더 또렷하고 조용하다.
export function SignalScale({ active }: { active: RecommendedStock["signalLight"] }) {
  return (
    <div className="flex items-center gap-[3px]" aria-hidden>
      {SIGNAL_ORDER.map((signal) => (
        <span
          key={signal}
          className="h-[3px] w-4 rounded-full"
          style={{
            backgroundColor:
              signal === active ? SIGNAL_META[signal].ink : "var(--color-track)",
          }}
        />
      ))}
    </div>
  );
}

// 카드 안 수치 한 칸. 라벨 → 값 → 부연 순서를 모든 칸에서 똑같이 맞춘다.
function Metric({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <span className="text-xs text-muted">{label}</span>
      {children}
      {hint && <span className="text-2xs text-faint">{hint}</span>}
    </div>
  );
}

export default function StockCard({
  stock,
  variant = "recommendation",
}: {
  stock: RecommendedStock;
  variant?: "recommendation" | "holding";
}) {
  const signal = SIGNAL_META[stock.signalLight];
  const grade = RISK_GRADE_META[stock.riskGrade];
  const topPercent = Math.round((1 - stock.rankPercentile) * 100);
  const bandLeft = clamp(50 + stock.returnBand.low * BAND_SCALE, 2, 94);
  const bandRight = clamp(50 + stock.returnBand.high * BAND_SCALE, bandLeft + 2, 98);
  const horizons = [
    ["H5", stock.horizonAgreement.h5],
    ["H10", stock.horizonAgreement.h10],
    ["H20", stock.horizonAgreement.h20],
  ] as const;
  const isHolding = variant === "holding";

  // 등급·플래그는 알약이 아니라 한 줄 메타 텍스트로 잇는다. 색은 신호 하나만 쓴다.
  const meta = [
    `${stock.code} · ${stock.market}`,
    `위험등급 ${stock.riskGrade} · ${grade.label}`,
    ...stock.riskFlags.map((flag) => RISK_FLAG_LABEL[flag]),
  ];

  return (
    <article
      className={`group flex flex-col gap-4 rounded-lg border border-line bg-white px-6 py-5 transition-shadow duration-200 hover:shadow-lift ${
        isHolding ? "border-l-[3px] border-l-edge" : ""
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="flex min-w-0 flex-col gap-1">
          <div className="flex items-baseline gap-2">
            <h3 className="truncate text-lg font-semibold">{stock.name}</h3>
            {isHolding && <span className="flex-none text-2xs text-faint">보유 알림</span>}
          </div>
          <p className="flex flex-wrap items-center gap-x-1.5 text-xs text-faint">
            {meta.map((item, i) => (
              <span key={item} className={grade.tone === "warn" && i === 1 ? "text-warn" : ""}>
                {i > 0 && <span className="mr-1.5 text-ghost">·</span>}
                {item}
              </span>
            ))}
          </p>
        </div>

        <div className="flex flex-none flex-col items-end gap-1.5">
          <span className="text-sm font-semibold" style={{ color: signal.ink }}>
            {signal.label}
          </span>
          <SignalScale active={stock.signalLight} />
          <span className="text-2xs text-faint tabular-nums">신호 강도 상위 {topPercent}%</span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 border-t border-line-soft pt-4 sm:grid-cols-[1.3fr_1fr_1fr] sm:gap-6">
        <Metric label={`예상 수익률 밴드 · ${Math.round(stock.returnBand.ciLevel * 100)}% 신뢰구간`}>
          <div className="relative h-1.5 rounded-full bg-track">
            <span className="absolute left-1/2 top-[-4px] h-[14px] w-px bg-edge" />
            <span
              className="absolute h-1.5 rounded-full"
              style={{
                left: `${bandLeft}%`,
                width: `${bandRight - bandLeft}%`,
                backgroundColor: signal.ink,
              }}
            />
          </div>
          <span className="text-base font-semibold tabular-nums">
            {formatPercent(stock.returnBand.low)} ~ {formatPercent(stock.returnBand.high)}
          </span>
        </Metric>

        <Metric
          label="과거 유사 신호 구간"
          hint={`유사 사례 ${stock.similarCaseCount}건 기준`}
        >
          <span className="text-base font-semibold tabular-nums">
            상승 비율 {Math.round(stock.hitRate * 100)}%
          </span>
        </Metric>

        <Metric label="기간별 신호 일치" hint={AGREEMENT_LABEL[stock.horizonAgreement.agreement]}>
          <div className="flex items-center gap-3">
            {horizons.map(([label, direction]) => (
              <span
                key={label}
                className="text-sm font-semibold tabular-nums"
                style={{ color: HORIZON_META[direction].ink }}
              >
                {label} {HORIZON_META[direction].arrow}
              </span>
            ))}
          </div>
        </Metric>
      </div>

      {stock.caution && (
        <p className="rounded-md bg-warn-tint px-3.5 py-2.5 text-xs text-warn">{stock.caution}</p>
      )}

      <div className="flex items-center justify-between gap-3">
        <SourceChip provenance={stock.provenance} />
        <Link
          href={`/stocks/${stock.code}`}
          className="text-xs font-medium text-muted transition-colors hover:text-brand hover:no-underline"
        >
          자세히 보기 →
        </Link>
      </div>
    </article>
  );
}
