import { MARKET_CONDITION_META } from "@/lib/display";
import SourceChip from "./source-chip";
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
  // 국내 관례: 상승 적색 / 하락 청색
  const color = positive
    ? "var(--color-up)"
    : negative
      ? "var(--color-down)"
      : "var(--color-muted)";
  const arrow = positive ? "▲" : negative ? "▼" : "";

  return (
    <div className="flex h-9 min-w-[112px] flex-col justify-center border-l border-line-soft px-3 first:border-l-0">
      <span className="text-2xs font-semibold text-muted">{quote.label}</span>
      <div className="flex items-baseline gap-1.5 whitespace-nowrap">
        <span className="text-sm font-semibold tabular-nums">{formatValue(quote)}</span>
        <span className="text-2xs font-medium tabular-nums" style={{ color }}>
          {arrow} {Math.abs(quote.changePercent).toFixed(2)}%
        </span>
      </div>
    </div>
  );
}

// 점수 산식이 정의되기 전(실데이터가 아닐 때)에는 숫자를 숨기고 "예시"만 둔다.
function Score({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="hidden items-baseline gap-1.5 whitespace-nowrap lg:flex">
      <span className="text-2xs text-faint">{label}</span>
      {value === null ? (
        <span className="text-xs font-medium text-faint">예시</span>
      ) : (
        <span className="text-xs font-semibold tabular-nums">{value}</span>
      )}
    </div>
  );
}

export default function MarketStatusBar({ status }: { status: MarketStatus }) {
  const meta = MARKET_CONDITION_META[status.condition];
  const real = status.provenance.kind === "real";

  return (
    <section aria-label="시장 지수와 시장 상태" className="border-t border-line bg-field">
      <div className="mx-auto grid h-[50px] w-full max-w-[1440px] grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-6 lg:grid-cols-[auto_minmax(0,1fr)_auto] lg:px-8">
        <div className="hidden min-w-[110px] flex-col lg:flex">
          <span className="text-2xs font-semibold text-muted">시장 브리핑</span>
          <span className="text-2xs font-medium tabular-nums">
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
          <SourceChip provenance={status.provenance} />
          <Score label="변동성" value={real ? status.volatilityScore : null} />
          <Score label="거래량" value={real ? status.volumeScore : null} />
          <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-xs font-medium">
            <span
              className="size-1.5 flex-none rounded-full"
              style={{ backgroundColor: meta.ink }}
              aria-hidden
            />
            <span style={{ color: meta.ink }}>{meta.label}</span>
          </span>
          <span className="hidden max-w-[250px] truncate text-2xs text-body xl:inline">
            {meta.comment}
          </span>
        </div>
      </div>
    </section>
  );
}
