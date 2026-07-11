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

// 수익률 밴드 바: 0%가 바 중앙(50%), 수익률 1%p당 5% 이동
const BAND_SCALE = 5;

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function formatPercent(value: number) {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

// 활성 도트만 신호 색, 비활성은 회색 — 5단계 중 현재 단계가 색으로 바로 구분되게
function SignalDots({ active }: { active: RecommendedStock["signalLight"] }) {
  return (
    <div className="flex items-center gap-[5px]">
      {SIGNAL_ORDER.map((signal) => {
        const dot = SIGNAL_META[signal].dot;
        return signal === active ? (
          <span
            key={signal}
            className="size-[13px] rounded-full"
            style={{ backgroundColor: dot, boxShadow: `0 0 0 3px ${dot}38` }}
          />
        ) : (
          <span key={signal} className="size-[9px] rounded-full bg-edge" />
        );
      })}
    </div>
  );
}

export default function StockCard({ stock }: { stock: RecommendedStock }) {
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

  return (
    <article className="flex flex-col gap-3.5 rounded-[14px] border border-line bg-white px-6 py-5 transition-shadow hover:border-[#c9d2e3] hover:shadow-[0_2px_12px_rgba(16,24,40,0.05)]">
      <div className="flex items-center gap-2.5">
        <span className="text-lg font-extrabold tracking-tight">{stock.name}</span>
        <span className="text-[13px] text-faint">
          {stock.code} · {stock.market}
        </span>
        <span
          className="inline-flex h-[22px] items-center rounded-md px-2 text-[11.5px] font-bold"
          style={{ backgroundColor: grade.bg, color: grade.text }}
        >
          위험등급 {stock.riskGrade} · {grade.label}
        </span>
        {stock.riskFlags.map((flag) => (
          <span
            key={flag}
            className="inline-flex h-[22px] items-center rounded-md bg-[#fdf1e3] px-2 text-[11.5px] font-bold text-[#b45814]"
          >
            {RISK_FLAG_LABEL[flag]}
          </span>
        ))}
        <div className="ml-auto flex items-center gap-3">
          <SignalDots active={stock.signalLight} />
          <span className="text-[13px] font-bold" style={{ color: signal.text }}>
            {signal.label} · 신호 강도 상위 {topPercent}%
          </span>
        </div>
      </div>

      <div className="grid grid-cols-[1.25fr_1fr_1fr] gap-6 border-t border-line-soft pt-3.5">
        <div className="flex flex-col gap-2">
          <span className="text-xs text-muted">
            예상 수익률 밴드{" "}
            <span className="text-ghost">
              · {Math.round(stock.returnBand.ciLevel * 100)}% 신뢰구간
            </span>
          </span>
          <div className="relative h-2 rounded-[4px] bg-track">
            <span className="absolute left-1/2 top-[-3px] h-3.5 w-px bg-[#c2cad6]" />
            <span
              className="absolute h-2 rounded-[4px]"
              style={{
                left: `${bandLeft}%`,
                width: `${bandRight - bandLeft}%`,
                background: `linear-gradient(90deg, ${signal.bandFrom}, ${signal.bandTo})`,
              }}
            />
          </div>
          <span className="text-sm font-bold tabular-nums">
            {formatPercent(stock.returnBand.low)} ~ {formatPercent(stock.returnBand.high)}
          </span>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted">과거 유사 신호 구간</span>
          <span className="text-[15px] font-extrabold">
            적중률 {Math.round(stock.hitRate * 100)}%
          </span>
          <span className="text-xs text-faint">유사 사례 {stock.similarCaseCount}건 기준</span>
        </div>

        <div className="flex flex-col gap-1.5">
          <span className="text-xs text-muted">단기·중기 신호 일치</span>
          <div className="flex items-center gap-1.5">
            {horizons.map(([label, direction]) => {
              const meta = HORIZON_META[direction];
              return (
                <span
                  key={label}
                  className="inline-flex h-[22px] items-center rounded-md px-2 text-[11.5px] font-bold"
                  style={{ backgroundColor: meta.bg, color: meta.text }}
                >
                  {label} {meta.arrow}
                </span>
              );
            })}
          </div>
          <span className="text-xs text-faint">
            {AGREEMENT_LABEL[stock.horizonAgreement.agreement]}
          </span>
        </div>
      </div>

      {stock.caution && (
        <div className="flex items-center gap-2.5 rounded-[10px] border border-[#f0e2bd] bg-[#fdf6e8] px-3.5 py-2.5">
          <span className="grid size-4 flex-none place-items-center rounded-full bg-[#d9a514] text-[10px] font-extrabold text-white">
            !
          </span>
          <span className="text-[13px] text-[#7a6210]">{stock.caution}</span>
        </div>
      )}

      <div className="flex justify-end">
        <Link href={`/stocks/${stock.code}`} className="text-[13px] font-semibold">
          근거 보기 →
        </Link>
      </div>
    </article>
  );
}
