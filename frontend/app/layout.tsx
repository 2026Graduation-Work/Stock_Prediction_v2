import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "시그널랩",
  description: "행동재무학 기반 심리 지수 반영 주가 신호 대시보드",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className="h-full">
      <body className="min-h-full">{children}</body>
    </html>
  );
}
