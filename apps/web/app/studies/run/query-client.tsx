"use client";

import { useSearchParams } from "next/navigation";
import { Card } from "@/components/ui";
import { RunProgressClient } from "../[id]/run/run-client";

export function RunQueryClient() {
  const searchParams = useSearchParams();
  const studyId = searchParams.get("id");
  const planCode = searchParams.get("plan");

  if (!studyId) {
    return (
      <div className="p-8">
        <Card>
          <h2 className="text-base font-semibold text-white">缺少研究编号</h2>
          <p className="text-xs text-neutral-400 mt-2">请从研究创建流程重新发起模拟。</p>
        </Card>
      </div>
    );
  }

  return <RunProgressClient studyId={studyId} planCode={planCode} />;
}
