import { Suspense } from "react";
import { AppShell, TopBar } from "@/components/layout";
import { ReportQueryClient } from "./query-client";

export const metadata = { title: "研究报告 — Thailand Market Twin" };

export default function ReportPage() {
  return (
    <AppShell>
      <TopBar title="研究报告" />
      <Suspense fallback={<div className="p-8 text-xs text-neutral-400">正在读取报告编号…</div>}>
        <ReportQueryClient />
      </Suspense>
    </AppShell>
  );
}
