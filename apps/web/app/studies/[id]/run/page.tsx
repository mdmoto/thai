import { AppShell, TopBar } from "@/components/layout";
import { RunProgressClient } from "./run-client";

export const metadata = { title: "模拟运行中 — Thailand Market Twin" };

export default function RunPage({ params }: { params: { id: string } }) {
  return (
    <AppShell>
      <TopBar title="模拟运行中" />
      <RunProgressClient studyId={params.id} />
    </AppShell>
  );
}
