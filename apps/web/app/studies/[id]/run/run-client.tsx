"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight, Loader2, RotateCcw } from "lucide-react";
import { Card } from "@/components/ui";
import { cn } from "@/lib/utils";

type RunStatus = "running" | "completed" | "failed";

const SERVER_STAGES = [
  { label: "扫描公开市场信息", detail: "读取客户提供的网页与 YouTube 公开资料，并记录来源和采集时间" },
  { label: "核验证据可信度", detail: "区分公开证据、模型先验与需要客户授权的平台数据" },
  { label: "准备 AI 模拟消费人群", detail: "读取泰国市场数据，生成本次分析所需的 AI 人群" },
  { label: "分析消费选择", detail: "比较产品卖点、价格、竞品和不购买等选择" },
  { label: "运行市场模拟", detail: "计算不同人群对各个方案的选择倾向" },
  { label: "比较方案与风险", detail: "测试价格变化、市场情景和结果波动" },
  { label: "生成决策报告", detail: "整理结论、依据、数据版本和使用限制" },
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
            <h2 className="text-xl font-semibold text-white tracking-tight">AI 市场模拟已完成</h2>
            <p className="text-xs text-neutral-400 font-light">
              后端耗时 {formatElapsed(elapsed)} · 报告编号 {reportId}
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
              <RotateCcw size={14} /> 重新运行
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <Loader2 size={22} className="animate-spin text-white mx-auto" />
            <div className="eyebrow">后台模拟正在运行</div>
            <h2 className="text-xl font-semibold text-white tracking-tight">
              正在采集市场信息并分析 AI 模拟消费人群…
            </h2>
            <p className="text-xs text-neutral-400 font-mono tabular-nums">
              已等待 {formatElapsed(elapsed)} · 深度决策通常需要 10–60 分钟
            </p>
            <p className="text-[10px] text-neutral-500">
              当前接口尚未返回分阶段进度，因此这里不会展示推测或虚构的完成百分比。
            </p>
          </div>
        )}
      </Card>

      <div className="space-y-3">
        <span className="eyebrow">本次分析内容</span>
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
