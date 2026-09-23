import { SERVICE_NAME } from "@/lib/brand";
import LogoMark from "./LogoMark";

// 마크 + "Take a Look" 글자. 마크는 글자 높이의 약 1.4배, 사이 여백은 마크 폭의 1/4.
export default function Wordmark({ size = 24, className = "" }: { size?: number; className?: string }) {
  return (
    <span className={`inline-flex items-center font-semibold text-brand ${className}`} style={{ gap: size / 4 }}>
      <LogoMark size={size} />
      <span>{SERVICE_NAME}</span>
    </span>
  );
}
