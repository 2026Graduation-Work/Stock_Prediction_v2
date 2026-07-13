import Dashboard from "./components/dashboard";
import {
  avoidanceNotice,
  holdingAlerts,
  investorProfile,
  marketStatus,
  portfolioHoldings,
  recommendedStocks,
} from "@/lib/mock-data";

export default function Home() {
  return (
    <Dashboard
      marketStatus={marketStatus}
      profile={investorProfile}
      stocks={recommendedStocks}
      holdingAlerts={holdingAlerts}
      holdings={portfolioHoldings}
      excludedStocks={avoidanceNotice.excludedStocks}
      avoidedLabels={avoidanceNotice.avoidedLabels}
    />
  );
}
