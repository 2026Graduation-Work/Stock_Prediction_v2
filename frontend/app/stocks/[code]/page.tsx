import { notFound } from "next/navigation";
import StockDetailView from "@/app/components/stock-detail";
import { investorProfile, marketStatus, stockDetails } from "@/lib/mock-data";

export function generateStaticParams() {
  return Object.keys(stockDetails).map((code) => ({ code }));
}

export default async function StockDetailPage({ params }: PageProps<"/stocks/[code]">) {
  const { code } = await params;
  const detail = stockDetails[code];
  if (!detail) notFound();

  return (
    <StockDetailView
      detail={detail}
      profile={investorProfile}
      marketStatus={marketStatus}
    />
  );
}
