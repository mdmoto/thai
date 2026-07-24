"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, RotateCcw } from "lucide-react";
import { getStudyApi, StudyDetail } from "@/lib/api-client";
import { Card, PlanBadge, StatusBadge } from "@/components/ui";

export function StudyViewClient() {
  const searchParams = useSearchParams();
  const studyId = searchParams.get("id");
  const [study, setStudy] = useState<StudyDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!studyId) return;
    getStudyApi(studyId)
      .then(setStudy)
      .catch(err => setError(err instanceof Error ? err.message : "读取项目失败"));
  }, [studyId]);

  if (!studyId) {
    return <div className="p-8 text-sm text-neutral-400">缺少项目编号。</div>;
  }
  if (error) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <Card><p className="text-sm text-rose-300">{error}</p></Card>
      </div>
    );
  }
  if (!study) {
    return <div className="p-8 text-sm text-neutral-400">正在读取项目…</div>;
  }

  const facts = study.facts || {};
  const canRun = ["READY", "FAILED_RECOVERABLE", "COMPLETED"].includes(study.status);

  return (
    <div className="p-5 sm:p-8 max-w-4xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-5">
        <div>
          <span className="eyebrow">Study</span>
          <h1 className="text-2xl font-semibold text-white mt-2">{study.name}</h1>
          <div className="flex items-center gap-2 mt-3">
            <StatusBadge status={study.status as Parameters<typeof StatusBadge>[0]["status"]} />
            <PlanBadge plan={study.plan_code as Parameters<typeof PlanBadge>[0]["plan"]} />
          </div>
        </div>
        <div className="flex gap-2">
          {study.status === "COMPLETED" && (
            <Link
              href={`/studies/report?id=${encodeURIComponent(study.id)}`}
              className="btn-cmai-secondary"
            >
              查看最近报告
            </Link>
          )}
          {canRun && (
            <Link
              href={`/studies/run?id=${encodeURIComponent(study.id)}&plan=${encodeURIComponent(study.plan_code)}`}
              className="btn-cmai-primary"
            >
              {study.status === "COMPLETED" ? <RotateCcw size={14} /> : <ArrowRight size={14} />}
              {study.status === "COMPLETED" ? "重新运行" : "开始运行"}
            </Link>
          )}
        </div>
      </div>

      <Card>
        <span className="eyebrow">Confirmed inputs</span>
        <div className="mt-4 divide-y divide-neutral-900 text-sm">
          <Fact label="研究类型" value={study.study_type} />
          <Fact label="品类" value={facts.category} />
          <Fact label="产品名称" value={facts.product_name} />
          <Fact label="价格" value={facts.price ? `฿${Number(facts.price).toLocaleString()}` : undefined} />
          <Fact label="参考价格" value={facts.reference_price ? `฿${Number(facts.reference_price).toLocaleString()}` : undefined} />
          <Fact label="竞品数量" value={Array.isArray(facts.competitor_data) ? `${facts.competitor_data.length} 个` : "0 个"} />
          <Fact label="品类面板版本" value={facts.category_panel_version} />
        </div>
      </Card>

      <Card>
        <span className="eyebrow">Interpretation</span>
        <p className="text-sm text-neutral-300 mt-3 leading-relaxed">
          本项目输出用于比较方案方向。人口与收入采用泰国公开宏观数据校准；
          若没有客户销售、选择实验或 A/B 数据，购买率和 WTP 会明确标记为先验预测。
        </p>
      </Card>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: unknown }) {
  if (value === undefined || value === null || value === "") return null;
  return (
    <div className="flex justify-between gap-6 py-3">
      <span className="text-neutral-500">{label}</span>
      <span className="text-white text-right break-all">{String(value)}</span>
    </div>
  );
}
