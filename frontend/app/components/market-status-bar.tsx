import { MARKET_CONDITION_META } from "@/lib/display";
import type { MarketIndexQuote, MarketStatus } from "@/lib/types";

function formatValue(quote: MarketIndexQuote): string {
  const fractionDigits = Number.isInteger(quote.value) ? 0 : 2;
  return quote.value.toLocaleString("ko-KR", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

function QuoteCell({ quote }: { quote: MarketIndexQuote }) {
  const positive = quote.change > 0;
  const negative = quote.change < 0;
  const color = positive ? "#c2413b" : negative ? "#2f5fd0" : "#667085";
  const arrow = positive ? "▲" : negative ? "▼" : "";

  return (
    <div className="flex h-9 min-w-[112px] flex-col justify-center border-l border-line-soft px-3 first:border-l-0">
      <span className="text-[10px] font-semibold text-muted">{quote.label}</span>
      <div className="flex items-baseline gap-1.5 whitespace-nowrap">
        <span className="text-[13px] font-extrabold tabular-nums">{formatValue(quote)}</span>
        <span className="text-[9.5px] font-bold tabular-nums" style={{ color }}>
          {arrow} {Math.abs(quote.changePercent).toFixed(2)}%
        </span>
      </div>
    </div>
  );
}

function Score({ label, value }: { label: string; value: number }) {
  return (
    <div className="hidden items-baseline gap-1.5 whitespace-nowrap lg:flex">
      <span className="text-[10px] text-faint">{label}</span>
      <span className="text-xs font-extrabold tabular-nums">{value}</span>
    </div>
  );
}

export default function MarketStatusBar({ status }: { status: MarketStatus }) {
  const meta = MARKET_CONDITION_META[status.condition];

  return (
    <section aria-label="시장 지수와 시장 상태" className="border-t border-line bg-field">
      <div className="mx-auto grid h-[50px] w-full max-w-[1440px] grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-6 lg:grid-cols-[auto_minmax(0,1fr)_auto] lg:px-8">
        <div className="hidden min-w-[110px] flex-col lg:flex">
          <span className="flex items-center gap-1.5 text-[10px] font-semibold text-muted">
            시장 브리핑
            {status.source === "mock" && (
              <span className="rounded-[3px] bg-brand-soft px-1 py-0.5 text-[8.5px] font-extrabold text-brand">
                샘플
              </span>
            )}
          </span>
          <span className="text-[11px] font-bold tabular-nums">
            {status.date.replaceAll("-", ".")} 기준
          </span>
        </div>

        <div className="flex min-w-0 items-center overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {status.indexQuotes.length > 0 ? (
            status.indexQuotes.map((quote) => <QuoteCell key={quote.symbol} quote={quote} />)
          ) : (
            <span className="px-3 text-xs text-faint">지수 데이터 미등록</span>
          )}
        </div>

        <div className="flex h-8 items-center gap-3 border-l border-line pl-3">
          <Score label="변동성" value={status.volatilityScore} />
          <Score label="거래량" value={status.volumeScore} />
          <span
            className="inline-flex h-6 items-center rounded-[4px] px-2.5 text-[10.5px] font-extrabold"
            style={{ backgroundColor: meta.bg, color: meta.color }}
          >
            {meta.label}
          </span>
          <span className="hidden max-w-[250px] truncate text-[10.5px] text-body xl:inline">
            {meta.comment}
          </span>
        </div>
      </div>
    </section>
  );
}
