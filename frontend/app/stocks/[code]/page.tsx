import { notFound } from "next/navigation";
import StockDetailBoundary from "@/app/components/stock-detail-boundary";
import { stockDetails } from "@/lib/mock-data";
import { loadStockInsights } from "@/lib/providers";
import { getMockStockDetailData } from "@/lib/queries";

// GitHub Actions가 매일 적재한 뉴스가 재배포 없이 화면에 반영되도록 한다.
export const revalidate = 3600;

export function generateStaticParams() {
  return Object.keys(stockDetails).map((code) => ({ code }));
}

export default async function StockDetailPage({ params }: PageProps<"/stocks/[code]">) {
  const { code } = await params;
  const initialData = getMockStockDetailData(code);
  if (!initialData) notFound();
  const insights = await loadStockInsights(code);

  return <StockDetailBoundary code={code} initialData={initialData} insights={insights} />;
}
