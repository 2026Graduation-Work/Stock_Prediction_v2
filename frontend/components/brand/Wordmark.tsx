import { SERVICE_NAME } from "@/lib/brand";
import LogoMark from "./LogoMark";

// 마크 + "Take a Look" 글자. 마크는 글자 높이의 약 1.4배, 사이 여백은 마크 폭의 1/4.
// compact: 좁은 화면(sm 미만)에서는 글자를 숨기고 마크만 보인다(글자는 스크린리더용으로 남김).
export default function Wordmark({
  size = 24,
  className = "",
  compact = false,
}: {
  size?: number;
  className?: string;
  compact?: boolean;
}) {
  return (
    <span className={`inline-flex items-center font-semibold text-brand ${className}`} style={{ gap: size / 4 }}>
      <LogoMark size={size} />
      <span className={compact ? "max-sm:sr-only" : undefined}>{SERVICE_NAME}</span>
    </span>
  );
}
