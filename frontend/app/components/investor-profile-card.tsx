import Link from "next/link";
import { INVESTMENT_HORIZON_LABEL } from "@/lib/display";
import type { InvestmentHorizon, InvestorProfileSummary } from "@/lib/types";

const HORIZON_SEGMENTS: InvestmentHorizon[] = ["short", "mid", "long"];

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col gap-[5px]">
      <div className="flex text-xs">
        <span className="text-muted">{label}</span>
        <span className="ml-auto font-medium tabular-nums">{value}</span>
      </div>
      <div className="h-[5px] rounded-full bg-track">
        <div className="h-full rounded-full bg-brand-accent" style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

export default function InvestorProfileCard({
  profile,
  avoidedLabels,
}: {
  profile: InvestorProfileSummary;
  avoidedLabels: string[];
}) {
  return (
    <section className="flex flex-col gap-3.5 surface px-5 py-[18px]">
      <div className="flex items-center">
        <span className="text-sm font-semibold">나의 투자 성향</span>
        <Link
          href="/survey"
          className="ml-auto inline-flex h-[26px] items-center whitespace-nowrap rounded-lg border border-edge bg-white px-2.5 text-xs font-medium text-body hover:border-ghost hover:bg-field hover:no-underline"
        >
          다시 진단
        </Link>
      </div>
      <div className="flex flex-col gap-1">
        <span className="inline-flex h-6 items-center self-start rounded-full bg-brand-soft px-3 text-xs font-medium text-brand">
          {profile.profileTypeLabel}
        </span>
        <span className="text-xs leading-5 text-body">{profile.personaLabel}</span>
      </div>
      <div className="flex flex-col gap-2.5">
        <ScoreBar label="위험 감수" value={profile.riskTolerance} />
        <ScoreBar label="흔들림 민감도" value={profile.sentimentSensitivity} />
        <div className="flex flex-col gap-[5px]">
          <div className="flex text-xs">
            <span className="text-muted">투자 기간</span>
            <span className="ml-auto font-medium">
              {INVESTMENT_HORIZON_LABEL[profile.horizon]}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-1">
            {HORIZON_SEGMENTS.map((segment) => (
              <span
                key={segment}
                className={`h-[5px] rounded-full ${
                  segment === profile.horizon ? "bg-brand-accent" : "bg-track"
                }`}
              />
            ))}
          </div>
        </div>
      </div>
      <div className="border-t border-line-soft pt-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-xs text-muted">회피 설정</span>
          {avoidedLabels.length > 0 ? (
            avoidedLabels.map((label) => (
              <span
                key={label}
                className="rounded-full bg-field px-2 py-1 text-2xs text-body"
              >
                {label}
              </span>
            ))
          ) : (
            <span className="text-xs text-muted">없음</span>
          )}
        </div>
      </div>
      <span className="text-xs text-muted">
        {profile.surveyedAt} 설문 기준 · 3축은 8축 설문을 묶어 요약한 값
      </span>
    </section>
  );
}
