import { MARKET_CONDITION_META } from "@/lib/display";
import type { MarketStatus } from "@/lib/types";

function ScoreMeter({ label, score, color }: { label: string; score: number; color: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs text-muted">{label}</span>
      <div className="flex items-center gap-2.5">
        <span className="text-[21px] font-extrabold leading-none tabular-nums">{score}</span>
        <div className="h-1.5 w-[130px] overflow-hidden rounded-[3px] bg-track">
          <div
            className="h-full rounded-[3px]"
            style={{ width: `${score}%`, backgroundColor: color }}
          />
        </div>
      </div>
    </div>
  );
}

export default function MarketStatusBar({ status }: { status: MarketStatus }) {
  const meta = MARKET_CONDITION_META[status.condition];
  return (
    <section className="flex items-center gap-9 rounded-[14px] border border-line bg-white px-6 py-[18px]">
      <div className="flex min-w-[130px] flex-col gap-0.5">
        <span className="text-[13px] font-bold text-body">오늘의 시장 상태</span>
        <span className="text-[11.5px] text-faint">{status.date.replaceAll("-", ".")} 기준</span>
      </div>
      <ScoreMeter label="변동성 점수" score={status.volatilityScore} color={meta.color} />
      <ScoreMeter label="거래량 점수" score={status.volumeScore} color={meta.color} />
      <div className="w-px self-stretch bg-track" />
      <div className="flex items-center gap-3.5">
        <span
          className="inline-flex h-[30px] items-center rounded-full px-4 text-sm font-extrabold"
          style={{ backgroundColor: meta.bg, color: meta.color }}
        >
          {meta.label}
        </span>
        <span className="text-sm text-body">{meta.comment}</span>
      </div>
    </section>
  );
}
