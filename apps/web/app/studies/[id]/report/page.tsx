import { AppShell, TopBar } from "@/components/layout";
import { ReportClient } from "./report-client";

export const metadata = { title: "研究报告 — Thailand Market Twin" };

export default function ReportPage({ params }: { params: { id: string } }) {
  return (
    <AppShell>
      <TopBar
        title="研究报告"
        actions={
          <div className="flex gap-2">
            <button className="btn-secondary text-sm px-3 py-2">分享</button>
            <button className="btn-primary text-sm px-3 py-2">下载 PDF</button>
          </div>
        }
      />
      <ReportClient studyId={params.id} />
    </AppShell>
  );
}
