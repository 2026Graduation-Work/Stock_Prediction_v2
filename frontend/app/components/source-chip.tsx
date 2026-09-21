import type { DataProvenance } from "@/lib/types";

// 수치 옆에 붙이는 출처 표시. 실데이터만 "출처 · 기준일 · 실데이터"로 쓰고,
// 나머지(픽스처·mock·데모 시드)는 모두 "예시 데이터"로 쓴다.
//
// 색 있는 알약이 아니라 조용한 회색 글씨로 둔다 — 출처는 늘 붙어 있는
// 각주지 경고가 아니다. 다만 "예시 데이터"는 신뢰와 직결되므로 점 하나로
// 구분해 눈에는 걸리게 한다.
export default function SourceChip({ provenance }: { provenance: DataProvenance }) {
  const real = provenance.kind === "real";
  const label = real
    ? [provenance.source, provenance.asOf?.replaceAll("-", "."), "실데이터"]
        .filter(Boolean)
        .join(" · ")
    : "예시 데이터";

  return (
    <span className="inline-flex flex-none items-center gap-1.5 whitespace-nowrap text-2xs text-faint">
      {!real && <span className="size-1 flex-none rounded-full bg-warn" aria-hidden />}
      {label}
    </span>
  );
}
