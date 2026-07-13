import Link from "next/link";
import { INVESTMENT_HORIZON_LABEL } from "@/lib/display";
import type { InvestmentHorizon, InvestorProfileSummary } from "@/lib/types";

const HORIZON_SEGMENTS: InvestmentHorizon[] = ["short", "mid", "long"];

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col gap-[5px]">
      <div className="flex text-xs">
        <span className="text-muted">{label}</span>
        <span className="ml-auto font-bold tabular-nums">{value}</span>
      </div>
      <div className="h-[5px] rounded-[3px] bg-track">
        <div className="h-full rounded-[3px] bg-brand" style={{ width: `${value}%` }} />
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
    <section className="flex flex-col gap-3.5 rounded-[14px] border border-line bg-white px-5 py-[18px]">
      <div className="flex items-center">
        <span className="text-sm font-extrabold">나의 투자 성향</span>
        <Link
          href="/survey"
          className="ml-auto inline-flex h-[26px] items-center whitespace-nowrap rounded-lg border border-edge bg-white px-2.5 text-[11.5px] font-semibold text-body hover:border-ghost hover:bg-field hover:no-underline"
        >
          설정 변경
        </Link>
      </div>
      <span className="inline-flex h-6 items-center self-start rounded-full bg-brand-soft px-3 text-xs font-bold text-brand">
        {profile.personaLabel}
      </span>
      <div className="flex flex-col gap-2.5">
        <ScoreBar label="위험 감수" value={profile.riskTolerance} />
        <ScoreBar label="심리 민감도" value={profile.sentimentSensitivity} />
        <div className="flex flex-col gap-[5px]">
          <div className="flex text-xs">
            <span className="text-muted">투자 기간</span>
            <span className="ml-auto font-bold">
              {INVESTMENT_HORIZON_LABEL[profile.horizon]}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-1">
            {HORIZON_SEGMENTS.map((segment) => (
              <span
                key={segment}
                className={`h-[5px] rounded-[3px] ${
                  segment === profile.horizon ? "bg-brand" : "bg-track"
                }`}
              />
            ))}
          </div>
        </div>
      </div>
      <div className="border-t border-line-soft pt-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-[11.5px] text-muted">회피 설정</span>
          {avoidedLabels.length > 0 ? (
            avoidedLabels.map((label) => (
              <span
                key={label}
                className="rounded-full bg-[#fff5f3] px-2 py-1 text-[10.5px] font-bold text-[#a83a31]"
              >
                {label}
              </span>
            ))
          ) : (
            <span className="text-[11.5px] text-faint">없음</span>
          )}
        </div>
      </div>
      <span className="text-[11.5px] text-faint">
        최초 설문({profile.surveyedAt}) 기준 · 성향·회피 항목은 설정에서 수정
      </span>
    </section>
  );
}
