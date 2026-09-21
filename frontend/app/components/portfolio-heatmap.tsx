import { SIGNAL_META } from "@/lib/display";
import type { DataProvenance, PortfolioHolding, SignalLight } from "@/lib/types";
import SourceChip from "./source-chip";

const LEGEND_SIGNALS: SignalLight[] = [
  "strong_negative",
  "negative",
  "neutral",
  "positive",
  "strong_positive",
];

interface WeightedHolding {
  holding: PortfolioHolding;
  amount: number;
}

function splitIntoColumns(holdings: PortfolioHolding[]): WeightedHolding[][] {
  const columns: WeightedHolding[][] = [[], []];
  const totals = [0, 0];
  const weighted = holdings
    .map((holding) => ({
      holding,
      amount: Math.max(holding.quantity * holding.avgBuyPrice, 1),
    }))
    .sort(
      (left, right) =>
        right.amount - left.amount || left.holding.code.localeCompare(right.holding.code),
    );

  for (const item of weighted) {
    const columnIndex = totals[0] <= totals[1] ? 0 : 1;
    columns[columnIndex].push(item);
    totals[columnIndex] += item.amount;
  }

  return columns.filter((column) => column.length > 0);
}

function formatAmount(amount: number): string {
  return `${Math.round(amount / 10_000).toLocaleString("ko-KR")}만원`;
}

export default function PortfolioHeatmap({ holdings }: { holdings: PortfolioHolding[] }) {
  const columns = splitIntoColumns(holdings);
  const columnTotals = columns.map((column) =>
    column.reduce((sum, item) => sum + item.amount, 0),
  );
  // 한 종목이라도 예시면 맵 전체를 예시로 표시한다.
  const provenance: DataProvenance | null =
    holdings.length === 0
      ? null
      : holdings.every(({ provenance: { kind } }) => kind === "real")
        ? holdings[0].provenance
        : { kind: "mock", source: "" };

  return (
    <section className="flex flex-col gap-3 rounded-md border border-line bg-white px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">내 포트폴리오 맵</h2>
          <p className="mt-0.5 text-2xs text-faint">면적은 등록 매입금액 기준</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="text-2xs text-muted">오늘 모델 신호</span>
          {provenance && <SourceChip provenance={provenance} />}
        </div>
      </div>

      {holdings.length === 0 ? (
        <div className="grid h-[252px] place-items-center border border-dashed border-edge bg-field text-xs text-muted">
          등록된 보유 종목이 없습니다
        </div>
      ) : (
        <div
          role="list"
          aria-label="보유 종목별 모델 신호 히트맵"
          className="flex h-[252px] min-w-0 gap-0.5 overflow-hidden bg-white"
        >
          {columns.map((column, columnIndex) => (
            <div
              key={column.map(({ holding }) => holding.code).join("-")}
              className="flex min-w-0 flex-col gap-0.5"
              style={{ flexGrow: columnTotals[columnIndex], flexBasis: 0 }}
            >
              {column.map(({ holding, amount }) => {
                const signal = SIGNAL_META[holding.signalLight];
                return (
                  <div
                    key={holding.code}
                    role="listitem"
                    title={`${holding.name} ${holding.code}, ${holding.quantity}주, 등록 매입금액 ${formatAmount(amount)}, ${signal.label} 신호`}
                    className="flex min-h-0 min-w-0 flex-col justify-between overflow-hidden p-3 text-white"
                    style={{ flexGrow: amount, flexBasis: 0, backgroundColor: signal.solid }}
                  >
                    <div className="min-w-0">
                      <div className="truncate text-base font-semibold">{holding.name}</div>
                      <div className="mt-0.5 text-2xs text-white/85">{holding.code}</div>
                    </div>
                    <div className="min-w-0">
                      <div className="truncate text-xs font-medium">{signal.label}</div>
                      <div className="mt-0.5 truncate text-2xs text-white/85">
                        {holding.quantity}주 · {formatAmount(amount)}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}

      <div>
        <div className="grid grid-cols-5 gap-0.5" aria-label="신호 색상 범례">
          {LEGEND_SIGNALS.map((signal) => (
            <div
              key={signal}
              className="h-1.5"
              style={{ backgroundColor: SIGNAL_META[signal].solid }}
            />
          ))}
        </div>
        <div className="mt-1 flex justify-between text-2xs text-faint">
          <span>강한 부정</span>
          <span>중립</span>
          <span>강한 긍정</span>
        </div>
      </div>
      <p className="text-2xs leading-4 text-faint">
        색상은 수익률이 아닌 오늘의 5단계 모델 신호입니다. 보유 수량과 평균 매입가는 수동
        등록값입니다.
      </p>
    </section>
  );
}
