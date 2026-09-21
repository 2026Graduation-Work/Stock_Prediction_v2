"use client";

import { CHART } from "@/lib/chart-colors";
import { useState } from "react";
import Link from "next/link";
import DisclaimerFooter from "./disclaimer-footer";
import InsightSection, { ScreenGuideBanner, useDemoStyleAxes } from "./insight-cards";
import SourceChip from "./source-chip";
import PriceHistoryChart from "./price-history-chart";
import ReturnHistogram from "./return-histogram";
import SiteHeader from "./site-header";
import { SignalScale } from "./stock-card";
import {
  AGREEMENT_LABEL,
  HORIZON_META,
  RISK_FLAG_LABEL,
  RISK_GRADE_META,
  SIGNAL_META,
} from "@/lib/display";
import { pricePeriod, type HoldingWeight, type StockInsights } from "@/lib/providers";
import type {
  InvestorProfileSummary,
  MarketStatus,
  StockDetail,
  StyleAxes,
} from "@/lib/types";

// 수익률 밴드 바: 0%가 바 중앙(50%), 수익률 1%p당 5% 이동 (stock-card와 동일 규칙)
const BAND_SCALE = 5;
const HORIZON_DAYS = { h5: 5, h10: 10, h20: 20 } as const;

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function formatPercent(value: number) {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function formatDate(iso: string) {
  return iso.replaceAll("-", ".");
}

function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  emphasized?: boolean;
  className?: string;
}) {
  return (
    <section className={`rounded-lg bg-white px-7 py-[22px] ${className}`}>
      {children}
    </section>
  );
}

function EvidenceUnavailable({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-[132px] place-items-center rounded-lg border border-dashed border-edge bg-field px-6 py-8 text-center text-sm leading-6 text-muted">
      <p className="m-0 max-w-[680px]">{children}</p>
    </div>
  );
}

interface StockDetailViewProps {
  detail: StockDetail;
  profile: InvestorProfileSummary;
  marketStatus: MarketStatus;
  maxRiskTier: number;
  styleAxes: StyleAxes | null;
  holdings: HoldingWeight[];
  insights: StockInsights;
  source: "mock" | "supabase";
  loading?: boolean;
  dataError?: string;
  onRetry?: () => void;
}

export default function StockDetailView({
  detail,
  profile,
  marketStatus,
  maxRiskTier,
  styleAxes,
  holdings,
  insights,
  source,
  loading = false,
  dataError = "",
  onRetry,
}: StockDetailViewProps) {
  const demo = useDemoStyleAxes(styleAxes);
  const [query, setQuery] = useState("");
  const [choice, setChoice] = useState<"watch" | "reduce" | "drop" | null>(null);

  const signal = SIGNAL_META[detail.signalLight];
  const grade = RISK_GRADE_META[detail.riskGrade];
  const topPercent = Math.round((1 - detail.rankPercentile) * 100);
  const ciPercent = Math.round(detail.returnBand.ciLevel * 100);
  const bandLeft = clamp(50 + detail.returnBand.low * BAND_SCALE, 2, 94);
  const bandRight = clamp(50 + detail.returnBand.high * BAND_SCALE, bandLeft + 2, 98);
  const asOfLabel = formatDate(detail.asOf).slice(5); // MM.DD
  const priceHistory = detail.priceHistory ?? [];
  const priceDataPeriod = pricePeriod(detail);
  const realizedReturns = detail.realizedReturns ?? [];
  const returnHorizon = detail.returnHorizon ?? "h10";
  const returnHorizonDays = HORIZON_DAYS[returnHorizon];
  const hasCurrentPrice =
    typeof detail.currentPrice === "number" &&
    Number.isFinite(detail.currentPrice) &&
    typeof detail.changePercent === "number" &&
    Number.isFinite(detail.changePercent);
  const changePercent = detail.changePercent ?? 0;
  const changeColor =
    changePercent > 0 ? "var(--color-sig-sn)" : changePercent < 0 ? "var(--color-brand)" : "var(--color-muted)";
  const changeArrow = changePercent > 0 ? "▲" : changePercent < 0 ? "▼" : "";
  const safeMaxRiskTier =
    Number.isInteger(maxRiskTier) && maxRiskTier >= 1 && maxRiskTier <= 5
      ? maxRiskTier
      : 4;
  const allowedRiskLabel =
    safeMaxRiskTier === 5 ? "5등급" : `${safeMaxRiskTier}~5등급`;
  const belowTolerance = detail.riskGrade < safeMaxRiskTier;
  const hasAiAdvice = Boolean(detail.aiAdvice?.trim());
  const horizons = [
    ["단기 H5 · 5거래일", detail.horizonAgreement.h5],
    ["중기 H10 · 10거래일", detail.horizonAgreement.h10],
    ["장기 H20 · 20거래일", detail.horizonAgreement.h20],
  ] as const;
  const choiceLabels = {
    watch: "관심 종목 추가",
    reduce: "비중 축소 검토",
    drop: "관심 해제",
  } as const;

  return (
    <div className="w-full">
      <SiteHeader
        query={query}
        onQueryChange={setQuery}
        profile={profile}
        marketStatus={marketStatus}
      />

      <div className="mx-auto box-border flex w-full max-w-[1104px] flex-col gap-4 px-8 pb-6 pt-5">
        <Link href="/" className="self-start text-sm text-muted hover:text-brand">
          ← 대시보드로 돌아가기
        </Link>

        {loading && (
          <div className="rounded-lg border border-edge bg-field px-4 py-3 text-sm font-semibold text-body">
            로그인한 사용자의 성향별 예측과 근거를 불러오는 중입니다.
          </div>
        )}

        {dataError && (
          <div
            role="alert"
            className="flex flex-col gap-3 rounded-lg bg-field px-4 py-3 sm:flex-row sm:items-center"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium text-body">
                실제 상세 데이터를 불러오지 못해 샘플 데이터를 표시합니다.
              </p>
              <p className="mt-1 break-words text-xs text-body">{dataError}</p>
            </div>
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="h-9 flex-none surface px-4 text-xs font-medium text-body hover:bg-field sm:ml-auto"
              >
                다시 시도
              </button>
            )}
          </div>
        )}

        {source === "supabase" &&
          (priceHistory.length < 2 || realizedReturns.length === 0) && (
            <div className="rounded-md bg-field px-4 py-3 text-sm text-body">
              예측·신뢰도·Top 근거는 Supabase 조회값입니다. 저장 계약이 없는 시세 이력과
              수익률 분포 원본은 샘플로 대체하지 않고 비워 둡니다.
            </div>
          )}

        {/* 종목 헤더 — 데이터 기준일과 예측 생성일은 하나의 날짜로 통일 */}
        <Card className="flex flex-wrap items-center gap-x-3.5 gap-y-2">
          <div className="flex flex-col gap-1.5">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-2xl font-semibold tracking-tight">{detail.name}</h1>
              <span className="text-sm text-muted">
                {detail.code} · {detail.market}
              </span>
              <span className={`text-sm ${grade.tone === "warn" ? "text-body" : "text-muted"}`}>
                위험등급 {detail.riskGrade} · {grade.label}
              </span>
              {detail.riskFlags.length > 0 && (
                <span className="text-sm text-body">
                  {detail.riskFlags.map((flag) => RISK_FLAG_LABEL[flag]).join(" · ")}
                </span>
              )}
              <SourceChip provenance={detail.provenance} />
            </div>
            <span className="text-xs text-muted">
              데이터·예측 기준일 {formatDate(detail.asOf)} · 장 마감 후 생성
            </span>
          </div>
          {hasCurrentPrice ? (
            <div className="ml-auto flex items-baseline gap-2.5">
              <span className="text-3xl font-semibold tabular-nums">
                {detail.currentPrice?.toLocaleString("ko-KR")}원
              </span>
              <span className="text-base font-medium tabular-nums" style={{ color: changeColor }}>
                {changeArrow} {formatPercent(changePercent)}
              </span>
            </div>
          ) : (
            <span className="ml-auto text-sm font-semibold text-muted">시세 데이터 미연결</span>
          )}
        </Card>

        {/* 성향 기반 인사이트: 첫 칸은 넛지, 이후 BIT 유형별 순서 */}
        <InsightSection
          detail={detail}
          insights={insights}
          holdings={holdings}
          demo={demo}
        />

        {/* 핵심 신호 */}
        <Card className="grid grid-cols-2 gap-7 xl:grid-cols-4">
          <div className="flex flex-col gap-2.5">
            <span className="text-xs text-muted">신호등</span>
            <SignalScale active={detail.signalLight} />
            <div className="flex flex-col gap-0.5">
              <span className="text-lg font-semibold" style={{ color: signal.ink }}>
                {signal.label}
              </span>
              <span className="text-xs text-muted">신호 강도 상위 {topPercent}%</span>
            </div>
          </div>

          <div className="flex flex-col gap-2.5 border-l border-line-soft pl-7">
            <span className="text-xs text-muted">
              예상 수익률 밴드 <span className="text-ghost">· {ciPercent}% 신뢰구간</span>
            </span>
            <div className="relative mt-1.5 h-2.5 rounded-full bg-track">
              <span className="absolute left-1/2 top-[-4px] h-[18px] w-px bg-edge" />
              <span
                className="absolute h-2.5 rounded-full"
                style={{
                  left: `${bandLeft}%`,
                  width: `${bandRight - bandLeft}%`,
                  backgroundColor: signal.ink,
                }}
              />
            </div>
            <span className="text-xl font-semibold tabular-nums">
              {formatPercent(detail.returnBand.low)} ~ {formatPercent(detail.returnBand.high)}
            </span>
            <span className="text-xs text-muted">
              과거 유사 신호 구간의 실현 수익률 분포
            </span>
          </div>

          <div className="flex flex-col gap-2.5 xl:border-l xl:border-line-soft xl:pl-7">
            <span className="text-xs text-muted">신뢰도</span>
            <span className="text-xl font-semibold">
              상승 비율 {Math.round(detail.hitRate * 100)}%
            </span>
            <span className="text-xs text-body">이 확률 구간에서 과거에 실제로 오른 비율</span>
            <span className="text-xs text-muted">과거 유사 사례 {detail.similarCaseCount}건</span>
          </div>

          <div className="flex flex-col gap-2.5 border-l border-line-soft pl-7">
            <span className="text-xs text-muted">기간별 신호 일치</span>
            <div className="flex flex-wrap items-center gap-3">
              {horizons.map(([label, direction]) => (
                <span
                  key={label}
                  className="text-base font-semibold tabular-nums"
                  style={{ color: HORIZON_META[direction].ink }}
                >
                  {label} {HORIZON_META[direction].arrow}
                </span>
              ))}
            </div>
            <span className="text-xs text-body">
              {AGREEMENT_LABEL[detail.horizonAgreement.agreement]}
            </span>
          </div>
        </Card>

        {/* 실현 수익률 분포 — 화이트박스 핵심 근거라 가장 눈에 띄게(강조 테두리) 배치 */}
        <Card emphasized className="flex flex-col gap-3">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-base font-semibold">
              과거 유사 신호 {detail.similarCaseCount}건의 실현 수익률 분포
            </span>
            <span className="text-xs text-muted">
              이 신호가 과거에 실제로 낸 결과 · 향후 {returnHorizonDays}거래일(
              {returnHorizon.toUpperCase()}) 기준
            </span>
            <span className="ml-auto inline-flex h-[22px] items-center rounded-md bg-brand-soft px-2 text-xs font-medium text-brand">
              {realizedReturns.length > 0 ? "예측 밴드의 출처" : "분포 원본 미연결"}
            </span>
          </div>
          {realizedReturns.length > 0 ? (
            <>
              <ReturnHistogram
                bins={realizedReturns}
                band={detail.returnBand}
                caseCount={detail.similarCaseCount}
                signal={signal}
              />
              <span className="text-xs text-muted">
                위 예상 수익률 밴드는 이 분포의 {ciPercent}% 구간입니다 · 미래 가격 경로가 아닌{" "}
                {returnHorizon.toUpperCase()} 시점의 분포 범위입니다
              </span>
            </>
          ) : (
            <EvidenceUnavailable>
              수익률 밴드와 유사 사례 수는 조회됐지만 분포 bin 원본은 DB에 저장되어 있지
              않습니다. 원본 저장 계약이 확정되면 히스토그램을 표시합니다.
            </EvidenceUnavailable>
          )}
        </Card>

        {/* 주가 흐름 — 과거 실선만, 미래 영역은 수익률 세로 구간 하나 */}
        <Card className="flex flex-col gap-3">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-base font-semibold">주가 흐름</span>
            <span className="text-xs text-muted">
              최근 60거래일 · 지난 주가만 표시(예측선 없음)
              {priceDataPeriod &&
                ` · 시세 데이터: ${priceDataPeriod.start} ~ ${priceDataPeriod.end}`}
            </span>
            <SourceChip provenance={detail.provenance} />
            {priceHistory.length >= 2 && (
              <div className="ml-auto flex items-center gap-3.5 text-xs text-muted">
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-0.5 w-3.5" style={{ backgroundColor: CHART.priceLine }} />
                  실제 주가
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span
                    className="box-border h-2.5 w-[7px] rounded-full border"
                    style={{ backgroundColor: signal.tint, borderColor: signal.ink }}
                  />
                  {returnHorizon.toUpperCase()} 분포 범위
                </span>
              </div>
            )}
          </div>
          {priceHistory.length >= 2 ? (
            <>
              <PriceHistoryChart
                prices={priceHistory}
                band={detail.returnBand}
                signal={signal}
                asOfLabel={asOfLabel}
              />
              <span className="text-xs text-muted">
                미래 가격 곡선은 그리지 않습니다 · 오른쪽 세로 구간은{" "}
                {returnHorizon.toUpperCase()} 시점 예상 수익률 범위({ciPercent}%)로, 위 분포
                히스토그램에서 나온 값입니다
              </span>
            </>
          ) : (
            <EvidenceUnavailable>
              최근 60거래일 종가가 DB에 저장되어 있지 않아 주가 흐름을 표시하지 않습니다.
            </EvidenceUnavailable>
          )}
        </Card>

        {/* 예측 근거 Top 3 */}
        <Card emphasized className="flex flex-col gap-4">
          <div className="flex items-baseline gap-2.5">
            <span className="text-base font-semibold">
              모델이 이 신호를 낸 이유{" "}
              <span className="text-brand">
                {detail.reasons.length > 0 ? `Top ${detail.reasons.length}` : "근거 없음"}
              </span>
            </span>
            <span className="text-xs text-muted">화이트박스 모델 · 기여도 순</span>
          </div>
          {detail.reasons.length > 0 ? (
            <div className="flex flex-col gap-3">
              {detail.reasons.map((reason, i) => {
                return (
                  <div
                    key={`${reason.source}:${reason.title}:${i}`}
                    className="flex flex-wrap items-center gap-x-3.5 gap-y-2 rounded-md bg-field px-4 py-3.5"
                  >
                    <span className="flex-none text-sm font-semibold tabular-nums text-ghost">
                      {i + 1}
                    </span>
                    <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
                      <span className="text-base font-medium">{reason.title}</span>
                      <span className="text-xs text-muted">{reason.detail}</span>
                    </div>
                    <span className="flex-none whitespace-nowrap text-2xs text-muted">
                      출처: {reason.sourceLabel}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <EvidenceUnavailable>
              이 예측에 연결된 근거 데이터가 없어 Top 근거를 표시할 수 없습니다.
            </EvidenceUnavailable>
          )}
        </Card>

        {/* 리스크 고지: 사용자 성향 수치와 연결하되 행동은 제안하지 않는다 */}
        <Card className="flex flex-col gap-3.5">
          <div className="flex items-center gap-2.5">
            <span className="text-base font-semibold">리스크 고지</span>
            {detail.riskFlags.map((flag) => (
              <span
                key={flag}
                className="inline-flex h-[22px] items-center rounded-md bg-sig-ng-tint px-2 text-xs font-medium text-sig-ng"
              >
                {RISK_FLAG_LABEL[flag]}
              </span>
            ))}
            <span className="inline-flex h-[22px] items-center rounded-md bg-track px-2 text-xs font-medium text-muted">
              {detail.market}
            </span>
          </div>
          {belowTolerance ? (
            <div className="flex gap-3 rounded-md bg-field px-4 py-3.5">
              <span className="mt-px grid size-[18px] flex-none place-items-center rounded-full bg-caution-mark text-2xs font-semibold text-white">
                !
              </span>
              <span className="text-sm leading-relaxed text-body">
                {profile.displayName}님의 위험 감수 성향({profile.riskTolerance})보다 변동성이 큰
                종목입니다. 위험 {detail.riskGrade}등급({grade.label})으로, 현재 성향 기준 허용
                범위({allowedRiskLabel}) 밖에 있습니다.
              </span>
            </div>
          ) : (
            <div className="flex gap-3 rounded-md border border-line bg-field px-4 py-3.5">
              <span className="mt-px grid size-[18px] flex-none place-items-center rounded-full bg-ghost text-2xs font-semibold text-white">
                i
              </span>
              <span className="text-sm leading-relaxed text-body">
                위험 {detail.riskGrade}등급({grade.label}) 종목으로, {profile.displayName}님의{" "}
                {profile.profileTypeLabel} 성향(위험 감수 {profile.riskTolerance}) 기준 허용
                범위({allowedRiskLabel}) 안에 있습니다.
              </span>
            </div>
          )}
        </Card>

        {/* AI 신호 해설 — LLM은 수치 번역만. 행동 제안은 아래 HITL 3버튼이 담당 */}
        {hasAiAdvice && (
          <Card className="flex flex-col gap-3">
            <div className="flex items-center gap-2.5">
              <span className="text-base font-semibold">AI 신호 해설</span>
              <span className="inline-flex h-[22px] items-center rounded-md bg-track px-2 text-xs font-medium text-muted">
                설명 전용 · 매매 조언 아님
              </span>
            </div>
            <p className="m-0 text-base leading-[1.7] text-body">
              {detail.aiAdvice}
            </p>
            <p className="m-0 text-xs leading-5 text-muted">
              AI가 생성한 설명은 부정확할 수 있습니다. 근거 수치와 출처를 확인한 뒤 최종 판단해
              주세요.
            </p>
          </Card>
        )}

        {/* 대응 선택지 (HITL) */}
        <Card className="flex flex-col gap-3">
          <span className="text-xs text-muted">
            서비스는 참고 정보를 제공하며, 최종 판단은 투자자 본인이 합니다 · 실제 주문이 실행되지
            않습니다
          </span>
          <div className="flex flex-wrap gap-2.5">
            {(Object.keys(choiceLabels) as (keyof typeof choiceLabels)[]).map((key) => {
              const selected = choice === key;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setChoice(key)}
                  className={`h-11 whitespace-nowrap rounded-md border px-5 text-sm font-medium transition-colors hover:border-brand ${
                    selected
                      ? "border-brand bg-brand-soft text-brand"
                      : "border-edge bg-white text-body"
                  }`}
                >
                  {choiceLabels[key]}
                </button>
              );
            })}
          </div>
          {choice && (
            <span className="text-sm font-semibold text-brand">
              &lsquo;{choiceLabels[choice]}&rsquo;가 참고용으로 기록되었습니다. 실제 주문은
              실행되지 않습니다.
            </span>
          )}
        </Card>
        <ScreenGuideBanner bit={demo.bit} />
      </div>

      <DisclaimerFooter fixed={false} />
    </div>
  );
}
