import Link from "next/link";
import type { InvestorProfileSummary } from "@/lib/types";

// 대시보드 맨 아래 작은 한 줄. 성향은 표시 순서·체크포인트에만 쓰고 종목을 거르지 않는다.
export default function InvestorProfileCard({
  profile,
  avoidedLabels,
}: {
  profile: InvestorProfileSummary;
  avoidedLabels: string[];
}) {
  return (
    <section
      aria-labelledby="my-profile-title"
      className="surface flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:gap-5"
    >
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <h2 id="my-profile-title" className="eyebrow">
          내 투자 성향 · {profile.surveyedAt} 진단
        </h2>
        <p className="text-sm text-body">
          <span className="font-semibold text-ink">{profile.profileTypeLabel}</span>
          {" — "}
          {profile.personaLabel}
        </p>
        <p className="text-xs text-muted">
          목록에서 빼 둔 종목: {avoidedLabels.length > 0 ? avoidedLabels.join(" · ") : "없음"}
        </p>
      </div>
      <Link href="/survey" className="btn-text flex-none">
        다시 진단
      </Link>
    </section>
  );
}
