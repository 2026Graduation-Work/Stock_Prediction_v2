// 브랜드 마크: 진녹 타일 아래에서 올라와 옆을 보는 고양이(docs/brand/README.md).
// 20px 이하는 눈을 뺀 단순형을 쓴다(작으면 눈이 뭉개진다).
export default function LogoMark({
  size = 28,
  label,
  className,
}: {
  size?: number;
  label?: string; // 글자 워드마크 없이 단독으로 쓸 때만 준다
  className?: string;
}) {
  const a11y = label ? { role: "img", "aria-label": label } : { "aria-hidden": true };
  if (size <= 20) {
    return (
      <svg width={size} height={size} viewBox="0 0 16 16" className={className} {...a11y}>
        <rect width="16" height="16" rx="3.5" fill="var(--color-logo-tile)" />
        <path fill="var(--color-logo-face)" d="M3 16v-6.5L3.5 4 6.5 6.5h3L12.5 4l.5 5.5V16Z" />
      </svg>
    );
  }
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={className} {...a11y}>
      <rect width="64" height="64" rx="15" fill="var(--color-logo-tile)" />
      <path
        fill="var(--color-logo-face)"
        d="M12 64V41c0-2.6.6-5 1.7-7.2L15 20l10.6 8.2c2-.5 4.1-.8 6.4-.8s4.4.3 6.4.8L49 20l1.3 13.8c1.1 2.2 1.7 4.6 1.7 7.2v23Z"
      />
      <circle cx="36" cy="43" r="3.4" fill="var(--color-logo-tile)" />
      <circle cx="45.5" cy="43" r="3.4" fill="var(--color-logo-tile)" />
      <circle cx="37" cy="42" r="1.3" fill="var(--color-logo-eye)" />
      <circle cx="46.5" cy="42" r="1.3" fill="var(--color-logo-eye)" />
    </svg>
  );
}

