import type { DataProvenance } from "@/lib/types";

// 수치 옆에 붙이는 출처 표시. 실데이터만 "출처 · 기준일 · 실데이터"로 쓰고,
// 나머지(픽스처·mock·데모 시드)는 모두 "예시 데이터"로 쓴다.
export default function SourceChip({ provenance }: { provenance: DataProvenance }) {
  const real = provenance.kind === "real";
  const label = real
    ? [provenance.source, provenance.asOf?.replaceAll("-", "."), "실데이터"]
        .filter(Boolean)
        .join(" · ")
    : "예시 데이터";

  return (
    <span
      className={`inline-flex h-[22px] flex-none items-center whitespace-nowrap rounded-md px-2 text-xs font-bold ${
        real ? "bg-[#e7f5ee] text-[#14735a]" : "bg-[#fff4d6] text-[#8a6100]"
      }`}
    >
      {label}
    </span>
  );
}
