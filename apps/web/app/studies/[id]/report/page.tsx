import { AppShell, TopBar } from "@/components/layout";
import { ReportClient } from "./report-client";

export const metadata = { title: "研究报告 — Thailand Market Twin" };

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

export default function ReportPage({ params }: { params: { id: string } }) {
  return (
    <AppShell>
      <TopBar
        title="研究报告"
        actions={
          <div className="flex gap-2">
            <button className="btn-cmai-secondary text-xs py-1.5 px-3">分享</button>
            <button className="btn-cmai-primary text-xs py-1.5 px-3">下载 PDF</button>
          </div>
        }
      />
      <ReportClient studyId={params.id} />
    </AppShell>
  );
}
