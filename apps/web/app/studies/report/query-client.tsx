"use client";

import { useSearchParams } from "next/navigation";
import { Card } from "@/components/ui";
import { ReportClient } from "../[id]/report/report-client";

export function ReportQueryClient() {
  const searchParams = useSearchParams();
  const reportId = searchParams.get("id");

  if (!reportId) {
    return (
      <div className="p-8">
        <Card>
          <h2 className="text-base font-semibold text-white">缺少报告编号</h2>
          <p className="text-xs text-neutral-400 mt-2">请从已完成的真实模拟任务进入报告。</p>
        </Card>
      </div>
    );
  }

  return <ReportClient reportId={reportId} />;
}
