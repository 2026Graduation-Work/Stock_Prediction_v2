import Dashboard from "./components/dashboard";
import {
  getHoldingAlerts,
  getMarketStatus,
  getPortfolio,
  getProfile,
  getRecommendedStocks,
} from "@/lib/queries";

export const dynamic = "force-dynamic";

export default async function Home() {
  const [marketStatus, stocks, holdingAlerts, holdings, profileResult] =
    await Promise.all([
      getMarketStatus(),
      getRecommendedStocks(),
      getHoldingAlerts(),
      getPortfolio(),
      getProfile(),
    ]);

  return (
    <Dashboard
      marketStatus={marketStatus}
      profile={profileResult.profile}
      stocks={stocks}
      holdingAlerts={holdingAlerts}
      holdings={holdings}
      excludedStocks={profileResult.excludedStocks}
      avoidedLabels={profileResult.avoidedLabels}
    />
  );
}
