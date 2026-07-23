import { AppShell, TopBar } from "@/components/layout";
import { RunProgressClient } from "./run-client";

export const metadata = { title: "模拟运行中 — Thailand Market Twin" };

export function generateStaticParams() {
  return [
    { id: "study_001" },
    { id: "study_002" },
    { id: "study_003" },
    { id: "study_004" },
    { id: "study_005" },
    { id: "demo" },
  ];
}

export default function RunPage({ params }: { params: { id: string } }) {
  return (
    <AppShell>
      <TopBar title="模拟运行中" />
      <RunProgressClient studyId={params.id} />
    </AppShell>
  );
}
