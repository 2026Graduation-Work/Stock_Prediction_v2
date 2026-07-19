"use client";

import { useState } from "react";
import Link from "next/link";
import DisclaimerFooter from "./disclaimer-footer";
import PriceHistoryChart from "./price-history-chart";
import ReturnHistogram from "./return-histogram";
import SiteHeader from "./site-header";
import { SignalDots } from "./stock-card";
import {
  AGREEMENT_LABEL,
  HORIZON_META,
  REASON_SOURCE_META,
  RISK_FLAG_LABEL,
  RISK_GRADE_META,
  SIGNAL_META,
} from "@/lib/display";
import type {
  InvestorProfileSummary,
  MarketStatus,
  RiskGrade,
  StockDetail,
} from "@/lib/types";

// 수익률 밴드 바: 0%가 바 중앙(50%), 수익률 1%p당 5% 이동 (stock-card와 동일 규칙)
const BAND_SCALE = 5;
const RANK_BADGE_BG = ["#2f5fd0", "#5c82db", "#8aa5e6"];
// 안정추구형 추천 허용선: 위험 4·5등급 (max_risk_tier 규칙)
const MIN_SAFE_GRADE: RiskGrade = 4;

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
  emphasized = false,
  className = "",
}: {
  children: React.ReactNode;
  emphasized?: boolean;
  className?: string;
}) {
  const border = emphasized ? "border-2 border-[#dbe4f6]" : "border border-line";
  return (
    <section className={`rounded-[14px] bg-white px-7 py-[22px] ${border} ${className}`}>
      {children}
    </section>
  );
}

interface StockDetailViewProps {
  detail: StockDetail;
  profile: InvestorProfileSummary;
  marketStatus: MarketStatus;
}

export default function StockDetailView({
  detail,
  profile,
  marketStatus,
}: StockDetailViewProps) {
  const [query, setQuery] = useState("");
  const [choice, setChoice] = useState<"watch" | "reduce" | "drop" | null>(null);

  const signal = SIGNAL_META[detail.signalLight];
  const grade = RISK_GRADE_META[detail.riskGrade];
  const topPercent = Math.round((1 - detail.rankPercentile) * 100);
  const ciPercent = Math.round(detail.returnBand.ciLevel * 100);
  const bandLeft = clamp(50 + detail.returnBand.low * BAND_SCALE, 2, 94);
  const bandRight = clamp(50 + detail.returnBand.high * BAND_SCALE, bandLeft + 2, 98);
  const asOfLabel = formatDate(detail.asOf).slice(5); // MM.DD
  const changeColor =
    detail.changePercent > 0 ? "#c93b34" : detail.changePercent < 0 ? "#2f5fd0" : "#667085";
  const changeArrow = detail.changePercent > 0 ? "▲" : detail.changePercent < 0 ? "▼" : "";
  const belowTolerance = detail.riskGrade < MIN_SAFE_GRADE;
  const hasAiAdvice = detail.aiAdvice.trim().length > 0;
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
    <div className="w-full pb-[72px]">
      <SiteHeader
        query={query}
        onQueryChange={setQuery}
        profile={profile}
        marketStatus={marketStatus}
      />

      <div className="mx-auto box-border flex w-full max-w-[1104px] flex-col gap-4 px-8 pb-6 pt-5">
        <Link href="/" className="self-start text-[13px] text-muted hover:text-brand">
          ← 대시보드로 돌아가기
        </Link>

        {/* 종목 헤더 — 데이터 기준일과 예측 생성일은 하나의 날짜로 통일 */}
        <Card className="flex flex-wrap items-center gap-x-3.5 gap-y-2">
          <div className="flex flex-col gap-1.5">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-2xl font-extrabold tracking-tight">{detail.name}</h1>
              <span className="text-sm text-faint">
                {detail.code} · {detail.market}
              </span>
              <span
                className="inline-flex h-[22px] items-center rounded-md px-2 text-[11.5px] font-bold"
                style={{ backgroundColor: grade.bg, color: grade.text }}
              >
                위험등급 {detail.riskGrade} · {grade.label}
              </span>
              {detail.riskFlags.map((flag) => (
                <span
                  key={flag}
                  className="inline-flex h-[22px] items-center rounded-md bg-[#fdf1e3] px-2 text-[11.5px] font-bold text-[#b45814]"
                >
                  {RISK_FLAG_LABEL[flag]}
                </span>
              ))}
            </div>
            <span className="text-[12.5px] text-faint">
              데이터·예측 기준일 {formatDate(detail.asOf)} · 장 마감 후 생성
            </span>
          </div>
          <div className="ml-auto flex items-baseline gap-2.5">
            <span className="text-[26px] font-extrabold tabular-nums">
              {detail.currentPrice.toLocaleString("ko-KR")}원
            </span>
            <span className="text-base font-bold tabular-nums" style={{ color: changeColor }}>
              {changeArrow} {formatPercent(detail.changePercent)}
            </span>
          </div>
        </Card>

        {/* 핵심 신호 */}
        <Card className="grid grid-cols-2 gap-7 xl:grid-cols-4">
          <div className="flex flex-col gap-2.5">
            <span className="text-xs text-muted">신호등</span>
            <SignalDots active={detail.signalLight} />
            <div className="flex flex-col gap-0.5">
              <span className="text-[17px] font-extrabold" style={{ color: signal.text }}>
                {signal.label}
              </span>
              <span className="text-xs text-faint">신호 강도 상위 {topPercent}%</span>
            </div>
          </div>

          <div className="flex flex-col gap-2.5 border-l border-line-soft pl-7">
            <span className="text-xs text-muted">위험 계층</span>
            <span
              className="inline-flex h-[30px] items-center self-start rounded-lg px-3.5 text-[15px] font-extrabold"
              style={{ backgroundColor: grade.bg, color: grade.text }}
            >
              {detail.riskGrade}등급 · {grade.label}
            </span>
            <div className="grid w-[110px] grid-cols-5 gap-[3px]">
              {([1, 2, 3, 4, 5] as const).map((tier) => (
                <span
                  key={tier}
                  className="h-[5px] rounded-[3px]"
                  style={{
                    backgroundColor: tier <= detail.riskGrade ? grade.text : "#eef1f5",
                    opacity: tier === detail.riskGrade ? 1 : tier < detail.riskGrade ? 0.35 : 1,
                  }}
                />
              ))}
            </div>
            <span className="text-[11.5px] text-faint">1=매우 위험 ~ 5=매우 안전</span>
          </div>

          <div className="flex flex-col gap-2.5 xl:border-l xl:border-line-soft xl:pl-7">
            <span className="text-xs text-muted">
              예상 수익률 밴드 <span className="text-ghost">· {ciPercent}% 신뢰구간</span>
            </span>
            <div className="relative mt-1.5 h-2.5 rounded-[5px] bg-track">
              <span className="absolute left-1/2 top-[-4px] h-[18px] w-px bg-[#c2cad6]" />
              <span
                className="absolute h-2.5 rounded-[5px]"
                style={{
                  left: `${bandLeft}%`,
                  width: `${bandRight - bandLeft}%`,
                  background: `linear-gradient(90deg, ${signal.bandFrom}, ${signal.bandTo})`,
                }}
              />
            </div>
            <span className="text-[19px] font-extrabold tabular-nums">
              {formatPercent(detail.returnBand.low)} ~ {formatPercent(detail.returnBand.high)}
            </span>
            <span className="text-[11.5px] text-faint">
              과거 유사 신호 구간의 실현 수익률 분포
            </span>
          </div>

          <div className="flex flex-col gap-2.5 border-l border-line-soft pl-7">
            <span className="text-xs text-muted">신뢰도</span>
            <span className="text-[19px] font-extrabold">
              적중률 {Math.round(detail.hitRate * 100)}%
            </span>
            <span className="text-[12.5px] text-body">이 확률 구간의 과거 적중률</span>
            <span className="text-xs text-faint">과거 유사 사례 {detail.similarCaseCount}건</span>
          </div>
        </Card>

        {/* 실현 수익률 분포 — 화이트박스 핵심 근거라 가장 눈에 띄게(강조 테두리) 배치 */}
        <Card emphasized className="flex flex-col gap-3">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-base font-extrabold">
              과거 유사 신호 {detail.similarCaseCount}건의 실현 수익률 분포
            </span>
            <span className="text-xs text-faint">
              이 신호가 과거에 실제로 낸 결과 · 향후 10거래일(H10) 기준
            </span>
            <span className="ml-auto inline-flex h-[22px] items-center rounded-md bg-brand-soft px-2 text-[11.5px] font-bold text-brand">
              예측 밴드의 출처
            </span>
          </div>
          <ReturnHistogram
            bins={detail.realizedReturns}
            band={detail.returnBand}
            caseCount={detail.similarCaseCount}
            signal={signal}
          />
          <span className="text-[11.5px] text-faint">
            예상 수익률 밴드 {formatPercent(detail.returnBand.low)} ~{" "}
            {formatPercent(detail.returnBand.high)}는 이 분포의 {ciPercent}% 구간입니다 · 미래
            가격 경로가 아닌 H10 시점의 분포 범위입니다
          </span>
        </Card>

        {/* 주가 흐름 — 과거 실선만, 미래 영역은 H10 세로 구간 하나 */}
        <Card className="flex flex-col gap-3">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-[15px] font-extrabold">주가 흐름</span>
            <span className="text-xs text-faint">최근 60거래일 · 실제 주가만 표시</span>
            <div className="ml-auto flex items-center gap-3.5 text-xs text-muted">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-0.5 w-3.5 bg-brand" />
                실제 주가
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span
                  className="box-border h-2.5 w-[7px] rounded-full border"
                  style={{ backgroundColor: `${signal.dot}29`, borderColor: signal.dot }}
                />
                H10 분포 범위
              </span>
            </div>
          </div>
          <PriceHistoryChart
            prices={detail.priceHistory}
            band={detail.returnBand}
            signal={signal}
            asOfLabel={asOfLabel}
          />
          <span className="text-[11.5px] text-faint">
            미래 가격 곡선은 그리지 않습니다 · 오른쪽 세로 구간은 H10 시점 예상 수익률 범위(
            {ciPercent}%)로, 위 분포 히스토그램에서 나온 값입니다
          </span>
        </Card>

        {/* 기간별 신호 일치 */}
        <Card className="flex flex-wrap items-center gap-x-5 gap-y-3">
          <span className="min-w-[150px] text-[15px] font-extrabold">기간별 신호 일치</span>
          <div className="flex flex-wrap items-center gap-2">
            {horizons.map(([label, direction]) => {
              const meta = HORIZON_META[direction];
              return (
                <span
                  key={label}
                  className="inline-flex h-[30px] items-center gap-1.5 rounded-lg px-3 text-[13px] font-bold"
                  style={{ backgroundColor: meta.bg, color: meta.text }}
                >
                  {label} {meta.arrow}
                </span>
              );
            })}
          </div>
          <div className="hidden w-px self-stretch bg-line-soft sm:block" />
          <span className="text-sm text-body">
            <strong className="text-ink">{AGREEMENT_LABEL[detail.horizonAgreement.agreement]}</strong>
          </span>
        </Card>

        {/* 예측 근거 Top 3 */}
        <Card emphasized className="flex flex-col gap-4">
          <div className="flex items-baseline gap-2.5">
            <span className="text-base font-extrabold">
              모델이 이 신호를 낸 이유 <span className="text-brand">Top 3</span>
            </span>
            <span className="text-xs text-faint">화이트박스 모델 · 기여도 순</span>
          </div>
          <div className="flex flex-col gap-3">
            {detail.reasons.map((reason, i) => {
              const source = REASON_SOURCE_META[reason.source];
              return (
                <div
                  key={reason.title}
                  className="flex flex-wrap items-center gap-x-3.5 gap-y-2 rounded-[10px] bg-field px-4 py-3.5"
                >
                  <span
                    className="grid size-[26px] flex-none place-items-center rounded-lg text-[13px] font-extrabold text-white"
                    style={{ backgroundColor: RANK_BADGE_BG[i] }}
                  >
                    {i + 1}
                  </span>
                  <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
                    <span className="text-[14.5px] font-bold">{reason.title}</span>
                    <span className="text-xs text-faint">{reason.detail}</span>
                  </div>
                  <span
                    className="inline-flex h-6 flex-none items-center rounded-md px-2.5 text-[11.5px] font-bold"
                    style={{ backgroundColor: source.bg, color: source.text }}
                  >
                    출처: {reason.sourceLabel}
                  </span>
                </div>
              );
            })}
          </div>
        </Card>

        {/* 리스크 고지: 사용자 성향 수치와 연결하되 행동은 제안하지 않는다 */}
        <Card className="flex flex-col gap-3.5">
          <div className="flex items-center gap-2.5">
            <span className="text-[15px] font-extrabold">리스크 고지</span>
            {detail.riskFlags.map((flag) => (
              <span
                key={flag}
                className="inline-flex h-[22px] items-center rounded-md bg-[#fdf1e3] px-2 text-[11.5px] font-bold text-[#b45814]"
              >
                {RISK_FLAG_LABEL[flag]}
              </span>
            ))}
            <span className="inline-flex h-[22px] items-center rounded-md bg-track px-2 text-[11.5px] font-bold text-muted">
              {detail.market}
            </span>
          </div>
          {belowTolerance ? (
            <div className="flex gap-3 rounded-[10px] border border-[#f0e2bd] bg-[#fdf6e8] px-4 py-3.5">
              <span className="mt-px grid size-[18px] flex-none place-items-center rounded-full bg-[#d9a514] text-[11px] font-extrabold text-white">
                !
              </span>
              <span className="text-[13.5px] leading-relaxed text-[#7a6210]">
                {profile.displayName}님의 위험 감수 성향({profile.riskTolerance})보다 변동성이 큰
                종목입니다. 위험 {detail.riskGrade}등급({grade.label})으로, 현재 성향 기준 허용
                범위(4·5등급) 밖에 있습니다.
              </span>
            </div>
          ) : (
            <div className="flex gap-3 rounded-[10px] border border-line bg-field px-4 py-3.5">
              <span className="mt-px grid size-[18px] flex-none place-items-center rounded-full bg-faint text-[11px] font-extrabold text-white">
                i
              </span>
              <span className="text-[13.5px] leading-relaxed text-body">
                위험 {detail.riskGrade}등급({grade.label}) 종목으로, {profile.displayName}님의{" "}
                {profile.profileTypeLabel} 성향(위험 감수 {profile.riskTolerance}) 기준 허용
                범위(4·5등급) 안에 있습니다.
              </span>
            </div>
          )}
        </Card>

        {/* AI 신호 해설 — LLM은 수치 번역만. 행동 제안은 아래 HITL 3버튼이 담당 */}
        {hasAiAdvice && (
          <Card className="flex flex-col gap-3">
            <div className="flex items-center gap-2.5">
              <span className="text-[15px] font-extrabold">AI 신호 해설</span>
              <span className="inline-flex h-[22px] items-center rounded-md bg-track px-2 text-[11.5px] font-bold text-muted">
                설명 전용 · 매매 조언 아님
              </span>
            </div>
            <p className="m-0 text-[14.5px] leading-[1.7] text-[#38404e]">
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
          <span className="text-xs text-faint">
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
                  className={`h-11 whitespace-nowrap rounded-[10px] border px-5 text-sm font-bold transition-colors hover:border-brand ${
                    selected
                      ? "border-brand bg-brand-soft text-brand"
                      : "border-edge bg-white text-[#38404e]"
                  }`}
                >
                  {choiceLabels[key]}
                </button>
              );
            })}
          </div>
          {choice && (
            <span className="text-[13px] font-semibold text-brand">
              &lsquo;{choiceLabels[choice]}&rsquo;가 참고용으로 기록되었습니다. 실제 주문은
              실행되지 않습니다.
            </span>
          )}
        </Card>
      </div>

      <DisclaimerFooter />
    </div>
  );
}
