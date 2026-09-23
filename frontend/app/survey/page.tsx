import type { Metadata } from "next";
import SurveyFlow from "./survey-flow";

export const metadata: Metadata = {
  title: "투자 성향 설문",
};

export default function SurveyPage() {
  return <SurveyFlow />;
}
