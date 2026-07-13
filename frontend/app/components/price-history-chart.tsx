"use client";

import { useRef, useState } from "react";
import type { SignalMeta } from "@/lib/display";
import type { ReturnBand } from "@/lib/types";

// 최근 60거래일 실제 주가 실선. 표현 규칙(미래 주가 곡선·부채꼴 금지)에 따라
// 미래 영역에는 H10 시점의 수익률 분포 범위를 나타내는 세로 구간 하나만 둔다.

const VB_W = 860;
const VB_H = 264;
const PAD = { top: 20, bottom: 34 };
const X0 = 14; // 실선 시작
const X1 = 668; // 실선 끝 = 오늘
const XH = 780; // H10 세로 구간 중심

function formatSigned(value: number) {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

// 눈금 간격을 1/2/2.5/5 × 10^n 으로 스냅
function niceStep(rough: number) {
  const power = 10 ** Math.floor(Math.log10(rough));
  const unit = rough / power;
  if (unit <= 1) return power;
  if (unit <= 2) return 2 * power;
  if (unit <= 2.5) return 2.5 * power;
  if (unit <= 5) return 5 * power;
  return 10 * power;
}

interface PriceHistoryChartProps {
  prices: number[];
  band: ReturnBand;
  signal: SignalMeta;
  asOfLabel: string; // 예: 07.07
}

export default function PriceHistoryChart({
  prices,
  band,
  signal,
  asOfLabel,
}: PriceHistoryChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hovered, setHovered] = useState<number | null>(null);

  const last = prices[prices.length - 1];
  const bandHighPrice = last * (1 + band.high / 100);
  const bandLowPrice = last * (1 + band.low / 100);
  const rawMin = Math.min(...prices, bandLowPrice);
  const rawMax = Math.max(...prices, bandHighPrice);
  const padValue = (rawMax - rawMin) * 0.08;
  const vMin = rawMin - padValue;
  const vMax = rawMax + padValue;

  const plotH = VB_H - PAD.top - PAD.bottom;
  const baseline = PAD.top + plotH;
  const y = (v: number) => PAD.top + ((vMax - v) / (vMax - vMin)) * plotH;
  const xAt = (i: number) => X0 + (i / (prices.length - 1)) * (X1 - X0);

  const step = niceStep((rawMax - rawMin) / 3);
  const ticks: number[] = [];
  for (let v = Math.ceil(vMin / step) * step; v <= vMax; v += step) ticks.push(v);

  const points = prices.map((p, i) => `${xAt(i).toFixed(1)},${y(p).toFixed(1)}`).join(" ");
  const yHigh = y(bandHighPrice);
  const yLow = y(bandLowPrice);

  const handleMove = (event: React.MouseEvent<SVGSVGElement>) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const vx = ((event.clientX - rect.left) / rect.width) * VB_W;
    if (vx < X0 || vx > X1 + 20) {
      setHovered(null);
      return;
    }
    const index = Math.round(((vx - X0) / (X1 - X0)) * (prices.length - 1));
    setHovered(Math.max(0, Math.min(prices.length - 1, index)));
  };

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${VB_W} ${VB_H}`}
        className="block w-full"
        role="img"
        aria-label={`최근 60거래일 주가 흐름. 10거래일 후 예상 수익률 범위 ${formatSigned(band.low)}부터 ${formatSigned(band.high)}까지`}
        onMouseMove={handleMove}
        onMouseLeave={() => setHovered(null)}
      >
        {/* 수평 그리드 + 가격 라벨 */}
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={X0} y1={y(tick)} x2={VB_W - 10} y2={y(tick)} stroke="#f0f2f5" />
            <text x={X0 + 4} y={y(tick) - 5} fontSize={11} fill="#98a2b3">
              {tick.toLocaleString("ko-KR")}
            </text>
          </g>
        ))}

        {/* 오늘 경계선 — 오른쪽 미래 영역에는 H10 세로 구간 외에 아무것도 그리지 않는다 */}
        <line x1={X1} y1={PAD.top} x2={X1} y2={baseline} stroke="#e4e7ec" />
        <text x={X0} y={baseline + 17} fontSize={11} fill="#98a2b3">
          60거래일 전
        </text>
        <text x={X1} y={baseline + 17} fontSize={11} fill="#98a2b3" textAnchor="end">
          오늘 ({asOfLabel})
        </text>

        {/* 실제 주가 실선 */}
        <polyline
          points={points}
          fill="none"
          stroke="#2f5fd0"
          strokeWidth={2}
          strokeLinejoin="round"
        />
        <circle cx={X1} cy={y(last)} r={4} fill="#2f5fd0" stroke="#ffffff" strokeWidth={1.5} />

        {/* H10 세로 구간: 분포 범위(경로 아님)를 캡슐 하나로 */}
        <rect
          x={XH - 8}
          y={yHigh}
          width={16}
          height={yLow - yHigh}
          rx={8}
          fill={signal.dot}
          opacity={0.16}
        />
        <line
          x1={XH - 11}
          y1={yHigh}
          x2={XH + 11}
          y2={yHigh}
          stroke={signal.dot}
          strokeWidth={2.5}
          strokeLinecap="round"
        />
        <line
          x1={XH - 11}
          y1={yLow}
          x2={XH + 11}
          y2={yLow}
          stroke={signal.dot}
          strokeWidth={2.5}
          strokeLinecap="round"
        />
        <line x1={XH} y1={yHigh + 3} x2={XH} y2={yLow - 3} stroke={signal.dot} strokeWidth={1.5} />
        <text
          x={XH}
          y={yHigh - 9}
          fontSize={12}
          fontWeight={700}
          fill={signal.text}
          textAnchor="middle"
        >
          {formatSigned(band.high)}
        </text>
        <text
          x={XH}
          y={yLow + 17}
          fontSize={12}
          fontWeight={700}
          fill={signal.text}
          textAnchor="middle"
        >
          {formatSigned(band.low)}
        </text>
        <text x={XH} y={baseline + 17} fontSize={11} fill="#98a2b3" textAnchor="middle">
          H10 · 10거래일 후
        </text>

        {/* 호버 크로스헤어 */}
        {hovered !== null && (
          <g pointerEvents="none">
            <line
              x1={xAt(hovered)}
              y1={PAD.top}
              x2={xAt(hovered)}
              y2={baseline}
              stroke="#c2cad6"
              strokeWidth={1}
            />
            <circle
              cx={xAt(hovered)}
              cy={y(prices[hovered])}
              r={4.5}
              fill="#2f5fd0"
              stroke="#ffffff"
              strokeWidth={2}
            />
          </g>
        )}
      </svg>

      {hovered !== null && (
        <div
          className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-lg border border-line bg-white px-2.5 py-1.5 shadow-[0_2px_10px_rgba(16,24,40,0.1)]"
          style={{
            left: `${(xAt(hovered) / VB_W) * 100}%`,
            top: `${((y(prices[hovered]) - 10) / VB_H) * 100}%`,
          }}
        >
          <span className="text-xs text-muted">
            {hovered === prices.length - 1 ? "오늘" : `${prices.length - 1 - hovered}거래일 전`}
          </span>
          <span className="ml-1.5 text-xs font-bold tabular-nums">
            {prices[hovered].toLocaleString("ko-KR")}원
          </span>
        </div>
      )}
    </div>
  );
}
