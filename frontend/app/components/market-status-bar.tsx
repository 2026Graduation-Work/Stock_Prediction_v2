import { MARKET_CONDITION_META } from "@/lib/display";
import SourceChip from "./source-chip";
import type { MarketIndexQuote, MarketStatus } from "@/lib/types";

// 헤더 아래 시장 브리핑: 지수 3개(등락 적/청) + 한 문장. 점수 숫자는 두지 않는다.
const SHOWN = new Set(["KOSPI", "KOSDAQ", "KOSPI200"]);

function formatValue(quote: MarketIndexQuote): string {
  return quote.value.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function Quote({ quote }: { quote: MarketIndexQuote }) {
  const color =
    quote.change > 0 ? "var(--color-up)" : quote.change < 0 ? "var(--color-down)" : "var(--color-muted)";
  const arrow = quote.change > 0 ? "▲" : quote.change < 0 ? "▼" : "";
  return (
    <span className="flex flex-none items-baseline gap-1.5 whitespace-nowrap">
      <span className="text-xs text-muted">{quote.label}</span>
      <span className="text-sm font-medium tabular-nums">{formatValue(quote)}</span>
      <span className="text-xs tabular-nums" style={{ color }}>
        {arrow}
        {Math.abs(quote.changePercent).toFixed(2)}%
      </span>
    </span>
  );
}

export default function MarketStatusBar({ status }: { status: MarketStatus }) {
  const meta = MARKET_CONDITION_META[status.condition];
  const quotes = status.indexQuotes.filter(({ symbol }) => SHOWN.has(symbol));

  return (
    <section aria-label="시장 브리핑" className="border-t border-line/60">
      <div className="mx-auto flex min-h-10 w-full max-w-[1200px] items-center gap-5 overflow-x-auto px-4 py-2 [scrollbar-width:none] sm:px-6 lg:px-8 [&::-webkit-scrollbar]:hidden">
        <span className="flex-none text-xs text-muted tabular-nums">시장 · {status.date.slice(5).replace("-", ".")}</span>
        {quotes.length > 0 ? (
          quotes.map((quote) => <Quote key={quote.symbol} quote={quote} />)
        ) : (
          <span className="text-xs text-muted">지수 데이터가 아직 없어요</span>
        )}
        <span className="flex-none whitespace-nowrap text-xs text-body lg:ml-auto">{meta.comment}</span>
        <SourceChip provenance={status.provenance} />
      </div>
    </section>
  );
}
