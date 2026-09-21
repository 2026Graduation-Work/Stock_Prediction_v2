import HoldingsEditor from "./holdings-editor";
import { getDashboardData } from "@/lib/queries";
import { KNOWN_STOCKS } from "@/lib/mock-data";

export default function PortfolioPage() {
  const { profile, marketStatus, holdings } = getDashboardData();
  return (
    <HoldingsEditor
      profile={profile}
      marketStatus={marketStatus}
      catalog={KNOWN_STOCKS}
      demoHoldings={holdings}
    />
  );
}
