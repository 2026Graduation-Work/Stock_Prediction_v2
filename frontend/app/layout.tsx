import type { Metadata } from "next";
import localFont from "next/font/local";
import OnboardingProvider from "./components/onboarding-provider";
import { SERVICE_DESCRIPTION, SERVICE_NAME, SERVICE_TAGLINE } from "@/lib/brand";
import "./globals.css";

const pretendard = localFont({
  src: "./fonts/PretendardVariable.woff2",
  display: "swap",
  weight: "45 920",
  variable: "--font-pretendard",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://stock-prediction-v2-chi.vercel.app"),
  title: { default: SERVICE_NAME, template: `%s · ${SERVICE_NAME}` },
  description: SERVICE_DESCRIPTION,
  applicationName: SERVICE_NAME,
  openGraph: {
    type: "website",
    locale: "ko_KR",
    siteName: SERVICE_NAME,
    title: `${SERVICE_NAME} — ${SERVICE_TAGLINE}`,
    description: SERVICE_DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
    title: `${SERVICE_NAME} — ${SERVICE_TAGLINE}`,
    description: SERVICE_DESCRIPTION,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className={`${pretendard.variable} h-full`}>
      <body className="min-h-full">
        <OnboardingProvider>{children}</OnboardingProvider>
      </body>
    </html>
  );
}
