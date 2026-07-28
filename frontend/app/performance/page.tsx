import PerformanceDashboard from "../components/performance-dashboard";
import { investorProfile, marketStatus } from "@/lib/mock-data";
import { performanceResults } from "@/lib/mock-performance";

export default function PerformancePage() {
  return (
    <PerformanceDashboard
      data={performanceResults}
      profile={investorProfile}
      marketStatus={marketStatus}
    />
  );
}
