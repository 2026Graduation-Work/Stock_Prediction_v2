import Dashboard from "./components/dashboard";
import {
  avoidanceNotice,
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
      holdings={portfolioHoldings}
      excludedCount={avoidanceNotice.excludedCount}
      avoidedLabels={avoidanceNotice.avoidedLabels}
    />
  );
}
