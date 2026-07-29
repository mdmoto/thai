"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  Loader2,
  RotateCcw,
} from "lucide-react";
import { Card } from "@/components/ui";
import {
  getRunStatusApi,
  runSimulationApi,
  SimulationRunStatus,
} from "@/lib/api-client";
import { cn } from "@/lib/utils";

type RunStatus = "running" | "completed" | "failed";

const SERVER_STAGES = [
  {
    code: "COLLECTING_PUBLIC_EVIDENCE",
    label: "扫描公开市场信息",
    detail: "后台执行多组泰文检索，读取公开评测、社媒、电商和视频资料",
  },
  {
    code: "COLLECTING_PUBLIC_EVIDENCE",
    label: "核验证据可信度",
    detail: "自动排除登录页、验证码、重复内容和无关主页，全程不需要客户授权账号",
  },
  {
    code: "GENERATING_POPULATION",
    label: "准备 AI 模拟消费人群",
    detail: "结合泰国人口、地区、收入与多维消费心理参数生成 AI 人群",
  },
  {
    code: "RUNNING_AGENTS",
    label: "分析完整决策旅程",
    detail: "模拟注意、理解、检索、比较、信任、支付摩擦和最终选择",
  },
  {
    code: "RUNNING_SIMULATION",
    label: "运行市场模拟",
    detail: "对 30 万 AI 模拟消费者执行多轮随机偏好与风险计算",
  },
  {
    code: "RUNNING_SIMULATION",
    label: "比较方案与风险",
    detail: "测试价格变化、市场情景和结果波动",
  },
  {
    code: "GENERATING_REPORT",
    label: "生成决策报告",
    detail: "整理结论、依据、数据版本和使用限制",
  },
];

const STAGE_RANK: Record<string, number> = {
  QUEUED: -2,
  PREPARING_POPULATION: -1,
  COLLECTING_PUBLIC_EVIDENCE: 0,
  GENERATING_POPULATION: 2,
  RUNNING_AGENTS: 3,
  RUNNING_SIMULATION: 4,
  GENERATING_REPORT: 6,
  COMPLETED: 7,
};

function createRequestKey(): string {
  const nonce =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `web-${nonce}`;
}

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
  const [serverStatus, setServerStatus] =
    useState<SimulationRunStatus | null>(null);

  const storageKey = useMemo(
    () => `market-twin-run:${studyId}:${planCode || "stored-plan"}`,
    [studyId, planCode],
  );

  useEffect(() => {
    if (status !== "running") return;
    const timer = window.setInterval(() => setElapsed(value => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [status, attempt]);

  useEffect(() => {
    let active = true;
    let pollTimer: number | null = null;
    let consecutivePollErrors = 0;

    const finish = (nextReportId: string) => {
      if (!active) return;
      window.localStorage.removeItem(storageKey);
      setReportId(nextReportId);
      setStatus("completed");
    };

    const fail = (message: string) => {
      if (!active) return;
      window.localStorage.removeItem(storageKey);
      setErrorMessage(message);
      setStatus("failed");
    };

    const poll = async (runJobId: string) => {
      if (!active) return;
      try {
        const current = await getRunStatusApi(runJobId);
        if (!active) return;
        consecutivePollErrors = 0;
        setServerStatus(current);
        if (current.status === "COMPLETED" && current.report_id) {
          finish(current.report_id);
          return;
        }
        if (current.status === "FAILED") {
          fail("后台任务没有完成，预留的积分或决策次数已自动退回。");
          return;
        }
        pollTimer = window.setTimeout(() => poll(runJobId), 5000);
      } catch {
        consecutivePollErrors += 1;
        if (consecutivePollErrors >= 6) {
          fail("暂时无法读取后台任务状态，请返回项目列表后重新进入。");
          return;
        }
        pollTimer = window.setTimeout(() => poll(runJobId), 8000);
      }
    };

    const startOrResume = async () => {
      setStatus("running");
      setReportId(null);
      setErrorMessage(null);
      setServerStatus(null);
      setElapsed(0);

      let requestKey = "";
      let savedRunJobId = "";
      try {
        const saved = JSON.parse(
          window.localStorage.getItem(storageKey) || "{}",
        ) as { requestKey?: string; runJobId?: string };
        requestKey = saved.requestKey || "";
        savedRunJobId = saved.runJobId || "";
      } catch {
        window.localStorage.removeItem(storageKey);
      }
      if (savedRunJobId) {
        await poll(savedRunJobId);
        return;
      }
      if (!requestKey) {
        requestKey = createRequestKey();
        window.localStorage.setItem(
          storageKey,
          JSON.stringify({ requestKey }),
        );
      }

      try {
        const result = await runSimulationApi({
          study_id: studyId,
          plan_code: planCode || undefined,
          idempotency_key: requestKey,
        });
        if (!active) return;
        if (result.report_id && !result.run_job_id) {
          finish(result.report_id);
          return;
        }
        if (!result.run_job_id) {
          throw new Error("后台已接收请求，但没有返回任务编号");
        }
        window.localStorage.setItem(
          storageKey,
          JSON.stringify({
            requestKey,
            runJobId: result.run_job_id,
          }),
        );
        if (result.status) {
          setServerStatus(result as SimulationRunStatus);
        }
        await poll(result.run_job_id);
      } catch (error) {
        fail(error instanceof Error ? error.message : "模拟执行失败");
      }
    };

    startOrResume();
    return () => {
      active = false;
      if (pollTimer !== null) window.clearTimeout(pollTimer);
    };
  }, [studyId, planCode, attempt, storageKey]);

  const retry = () => {
    window.localStorage.removeItem(storageKey);
    setAttempt(value => value + 1);
  };
  const formatElapsed = (seconds: number) =>
    `${Math.floor(seconds / 60)}:${(seconds % 60).toString().padStart(2, "0")}`;
  const activeRank = STAGE_RANK[serverStatus?.stage || "QUEUED"] ?? -2;

  return (
    <div className="max-w-3xl mx-auto p-5 sm:p-8 space-y-8">
      <Card className="text-center py-10">
        {status === "completed" && reportId ? (
          <div className="space-y-3">
            <div className="w-10 h-10 rounded-full bg-white text-black font-bold flex items-center justify-center mx-auto text-lg">
              ✓
            </div>
            <h2 className="text-xl font-semibold text-white tracking-tight">
              AI 市场模拟已完成
            </h2>
            <p className="text-xs text-neutral-400 font-light">
              后台耗时 {formatElapsed(elapsed)} · 报告编号 {reportId}
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
            <h2 className="text-xl font-semibold text-white tracking-tight">
              模拟没有完成
            </h2>
            <p className="text-xs text-red-300/80 max-w-lg mx-auto">
              {errorMessage}
            </p>
            <button
              onClick={retry}
              className="btn-cmai-secondary inline-flex mt-2"
            >
              <RotateCcw size={14} /> 重新运行
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <Loader2 size={22} className="animate-spin text-white mx-auto" />
            <div className="eyebrow">后台深度决策正在运行</div>
            <h2 className="text-xl font-semibold text-white tracking-tight">
              {serverStatus?.stage_label || "正在安全提交后台任务…"}
            </h2>
            <p className="text-xs text-neutral-400 font-mono tabular-nums">
              已运行 {formatElapsed(elapsed)}
              {serverStatus
                ? ` · 流程节点 ${serverStatus.progress_percent}%`
                : ""}
            </p>
            <p className="text-[11px] text-emerald-300/80">
              可以关闭此页面。服务器会继续采集和计算，稍后重新进入项目即可查看进度。
            </p>
          </div>
        )}
      </Card>

      <div className="space-y-3">
        <span className="eyebrow">本次分析内容</span>
        <div className="space-y-2">
          {SERVER_STAGES.map((stage, index) => {
            const completed = status === "completed" || activeRank > index;
            const active = status === "running" && activeRank === index;
            return (
              <Card
                key={`${stage.label}-${index}`}
                className={cn(
                  "!p-4",
                  completed && "border-neutral-700",
                  active && "border-blue-500/60 bg-blue-500/[0.04]",
                  status === "failed" && "border-red-950",
                )}
              >
                <div className="flex items-center gap-4">
                  <div
                    className={cn(
                      "w-7 h-7 rounded-full flex items-center justify-center text-xs font-mono font-medium shrink-0",
                      completed
                        ? "bg-white text-black"
                        : active
                          ? "bg-blue-500 text-white"
                          : status === "failed"
                            ? "bg-red-950 text-red-300 border border-red-900"
                            : "bg-neutral-900 text-neutral-400 border border-neutral-800",
                    )}
                  >
                    {completed ? <Check size={14} /> : index + 1}
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-white">
                      {stage.label}
                    </div>
                    <p className="text-[11px] text-neutral-400 font-light mt-0.5">
                      {stage.detail}
                    </p>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
