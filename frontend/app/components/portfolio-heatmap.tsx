import { SIGNAL_META } from "@/lib/display";
import type { PortfolioHolding } from "@/lib/types";

export default function PortfolioHeatmap({ holdings }: { holdings: PortfolioHolding[] }) {
  return (
    <section className="flex flex-col gap-3 rounded-[14px] border border-line bg-white px-5 py-[18px]">
      <span className="text-sm font-extrabold">내 포트폴리오 히트맵</span>
      <div className="grid grid-cols-2 gap-2">
        {holdings.map((holding) => {
          const signal = SIGNAL_META[holding.signalLight];
          return (
            <div
              key={holding.code}
              className="flex flex-col gap-1.5 rounded-[10px] border p-3"
              style={{ backgroundColor: signal.heatBg, borderColor: signal.heatBorder }}
            >
              <span
                className="size-2.5 rounded-full"
                style={{ backgroundColor: signal.dot }}
              />
              <span className="text-[13px] font-bold">{holding.name}</span>
              <span className="text-[11.5px] font-semibold" style={{ color: signal.text }}>
                {signal.label}
              </span>
            </div>
          );
        })}
      </div>
      <span className="text-[11.5px] text-faint">
        색상 = 오늘 신호 강도 · 계좌 연동이 아닌 수동 등록 기준
      </span>
    </section>
  );
}
