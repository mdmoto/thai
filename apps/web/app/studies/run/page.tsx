import { Suspense } from "react";
import { AppShell, TopBar } from "@/components/layout";
import { RunQueryClient } from "./query-client";

export const metadata = { title: "模拟运行中 — Thailand Market Twin" };

export default function RunPage() {
  return (
    <AppShell>
      <TopBar title="模拟运行中" />
      <Suspense fallback={<div className="p-8 text-xs text-neutral-400">正在读取研究任务…</div>}>
        <RunQueryClient />
      </Suspense>
    </AppShell>
  );
}
