import Dashboard from "./components/dashboard";
import { getDashboardData } from "@/lib/queries";

export const dynamic = "force-dynamic";

export default async function Home() {
  return <Dashboard {...(await getDashboardData())} />;
}
