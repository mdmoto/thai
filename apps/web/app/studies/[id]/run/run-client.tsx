"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight, Loader2, RotateCcw } from "lucide-react";
import { Card } from "@/components/ui";
import { cn } from "@/lib/utils";

type RunStatus = "running" | "completed" | "failed";

const SERVER_STAGES = [
  { label: "合成人口准备", detail: "读取校准版本并生成本次研究人口" },
  { label: "代表样本研究", detail: "生成结构化弱信号；不可用时不会使用 mock Persona" },
  { label: "离散选择模拟", detail: "运行行业模型、竞品选择集与不购买选项" },
  { label: "不确定性与情景", detail: "计算先验预测区间、价格弹性和动态扩散" },
  { label: "报告与血缘", detail: "保存数据版本、模型版本、假设和限制" },
];

export function RunProgressClient({
  studyId,
  planCode,
}: {
  studyId: string;
  planCode?: string | null;
}) {
  const [status, setStatus] = useState<RunStatus>("running");
  const [reportId, setReportId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const sessionNonce = useRef(
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`,
  );
  const requestRef = useRef<{ key: string; promise: Promise<{ report_id?: string }> } | null>(null);

  useEffect(() => {
    if (status !== "running") return;
    const timer = window.setInterval(() => setElapsed(value => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [status, attempt]);

  useEffect(() => {
    let active = true;
    setStatus("running");
    setReportId(null);
    setErrorMessage(null);
    setElapsed(0);

    const requestKey = `${studyId}:${planCode || "stored-plan"}:${attempt}`;
    if (!requestRef.current || requestRef.current.key !== requestKey) {
      requestRef.current = {
        key: requestKey,
        promise: (async () => {
          const { runSimulationApi } = await import("@/lib/api-client");
          return runSimulationApi({
            study_id: studyId,
            plan_code: planCode || undefined,
            idempotency_key: `web-${sessionNonce.current}-${attempt}`,
          });
        })(),
      };
    }

    requestRef.current.promise
      .then(report => {
        if (!report?.report_id) {
          throw new Error("后端完成了请求，但没有返回报告编号");
        }
        if (active) {
          setReportId(report.report_id);
          setStatus("completed");
        }
      })
      .catch(error => {
        if (active) {
          setErrorMessage(error instanceof Error ? error.message : "模拟执行失败");
          setStatus("failed");
        }
      });

    return () => {
      active = false;
    };
  }, [studyId, planCode, attempt]);

  const formatElapsed = (seconds: number) =>
    `${Math.floor(seconds / 60)}:${(seconds % 60).toString().padStart(2, "0")}`;

  return (
    <div className="max-w-3xl mx-auto p-8 space-y-8">
      <Card className="text-center py-10">
        {status === "completed" && reportId ? (
          <div className="space-y-3">
            <div className="w-10 h-10 rounded-full bg-white text-black font-bold flex items-center justify-center mx-auto text-lg">
              ✓
            </div>
            <h2 className="text-xl font-semibold text-white tracking-tight">真实模拟已完成</h2>
            <p className="text-xs text-neutral-400 font-light">
              后端耗时 {formatElapsed(elapsed)} · Report ID {reportId}
            </p>
            <Link
              href={`/studies/report?id=${encodeURIComponent(reportId)}`}
              className="btn-cmai-primary inline-flex mt-2"
            >
              查看报告结果 <ArrowRight size={14} />
            </Link>
          </div>
        ) : status === "failed" ? (
          <div className="space-y-3">
            <AlertTriangle size={24} className="text-red-400 mx-auto" />
            <h2 className="text-xl font-semibold text-white tracking-tight">模拟没有完成</h2>
            <p className="text-xs text-red-300/80 max-w-lg mx-auto">{errorMessage}</p>
            <button
              onClick={() => setAttempt(value => value + 1)}
              className="btn-cmai-secondary inline-flex mt-2"
            >
              <RotateCcw size={14} /> 重试真实任务
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <Loader2 size={22} className="animate-spin text-white mx-auto" />
            <div className="eyebrow">Backend Simulation Running</div>
            <h2 className="text-xl font-semibold text-white tracking-tight">
              正在运行真实选择模型与情景模拟…
            </h2>
            <p className="text-xs text-neutral-400 font-mono tabular-nums">
              已等待 {formatElapsed(elapsed)} · 完成时间取决于套餐、人口和轮数
            </p>
            <p className="text-[10px] text-neutral-500">
              当前 API 尚未返回分阶段事件，因此这里不显示虚构百分比。
            </p>
          </div>
        )}
      </Card>

      <div className="space-y-3">
        <span className="eyebrow">Server Execution Contract</span>
        <div className="space-y-2">
          {SERVER_STAGES.map((stage, index) => (
            <Card
              key={stage.label}
              className={cn(
                "!p-4",
                status === "completed" && "border-neutral-700",
                status === "failed" && "border-red-950",
              )}
            >
              <div className="flex items-center gap-4">
                <div
                  className={cn(
                    "w-7 h-7 rounded-full flex items-center justify-center text-xs font-mono font-medium shrink-0",
                    status === "completed"
                      ? "bg-white text-black"
                      : status === "failed"
                        ? "bg-red-950 text-red-300 border border-red-900"
                        : "bg-neutral-900 text-neutral-400 border border-neutral-800",
                  )}
                >
                  {status === "completed" ? "✓" : index + 1}
                </div>
                <div>
                  <div className="text-xs font-semibold text-white">{stage.label}</div>
                  <p className="text-[11px] text-neutral-400 font-light mt-0.5">{stage.detail}</p>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
