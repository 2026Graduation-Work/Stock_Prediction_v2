import PerformanceDashboard from "../components/performance-dashboard";
import { investorProfile, marketStatus } from "@/lib/mock-data";
import { loadPerformanceData } from "@/lib/performance-data";

export default async function PerformancePage() {
  const { data, isSample, conclusion } = await loadPerformanceData();

  return (
    <PerformanceDashboard
      data={data}
      isSample={isSample}
      conclusion={conclusion}
      profile={investorProfile}
      marketStatus={marketStatus}
    />
  );
}
