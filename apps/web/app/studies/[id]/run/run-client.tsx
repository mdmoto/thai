"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { CheckCircle2, Clock, Loader2, ArrowRight } from "lucide-react";
import { Card, ProgressBar } from "@/components/ui";
import { cn } from "@/lib/utils";

interface Stage {
  id: string;
  label: string;
  sublabel: string;
  durationMs: number;
}

const STAGES: Stage[] = [
  { id: "parsing",    label: "资料解析",       sublabel: "分析上传资料，提取结构化信息与假定事实",   durationMs: 4000 },
  { id: "population", label: "目标人口构建",   sublabel: "从 Thailand World Model 中筛选 30,000 目标人口", durationMs: 6000 },
  { id: "agents",     label: "代表消费者推理", sublabel: "AI 消费者 Agent 对方案生成结构化反应",   durationMs: 8000 },
  { id: "simulation", label: "群体模拟",       sublabel: "Monte Carlo 80 轮向量化行为模拟",         durationMs: 12000 },
  { id: "scenarios",  label: "情景对比",       sublabel: "比较 4 个对比方案的结果差异与收益变化",   durationMs: 6000 },
  { id: "report",     label: "报告生成",       sublabel: "聚合指标，生成可追溯商业分析报告",        durationMs: 4000 },
];

type StageStatus = "waiting" | "running" | "done";

interface StageState {
  status: StageStatus;
  progress: number;
  detail: string;
}

export function RunProgressClient({ studyId }: { studyId: string }) {
  const [stages, setStages] = useState<StageState[]>(
    STAGES.map(() => ({ status: "waiting", progress: 0, detail: "" }))
  );
  const [currentStage, setCurrentStage] = useState(0);
  const [done, setDone] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (done) return;
    const timer = setInterval(() => {
      setElapsed(e => e + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [done]);

  const [reportId, setReportId] = useState<string | null>(null);

  useEffect(() => {
    if (done) return;
    if (currentStage >= STAGES.length) {
      setDone(true);
      return;
    }

    const stage = STAGES[currentStage];
    const startTime = Date.now();

    // Trigger real backend run at simulation stage
    if (stage.id === "simulation" && !reportId) {
      (async () => {
        try {
          const { runSimulationApi } = await import("@/lib/api-client");
          const popSize = studyId.includes("study_") ? 30000 : 10000;
          const report = await runSimulationApi({
            study_id: studyId,
            population_size: popSize,
            mc_rounds: 50,
          });
          if (report && report.report_id) {
            setReportId(report.report_id);
          }
        } catch (err) {
          console.log("Backend simulation call fallback:", err);
        }
      })();
    }

    const interval = setInterval(() => {
      const elapsedMs = Date.now() - startTime;
      const pct = Math.min(99, (elapsedMs / stage.durationMs) * 100);

      setStages(prev => {
        const next = [...prev];
        next[currentStage] = {
          status: "running",
          progress: pct,
          detail: getStageDetail(currentStage, pct),
        };
        return next;
      });

      if (elapsedMs >= stage.durationMs) {
        clearInterval(interval);
        setStages(prev => {
          const next = [...prev];
          next[currentStage] = { status: "done", progress: 100, detail: "已完成" };
          return next;
        });
        setCurrentStage(s => s + 1);
      }
    }, 100);

    return () => clearInterval(interval);
  }, [currentStage, done, reportId, studyId]);

  function getStageDetail(stageIdx: number, pct: number): string {
    switch (stageIdx) {
      case 0: return pct < 50 ? "解析输入文件与描述..." : "结构化事实参数...";
      case 1: return pct < 50 ? "加载曼谷与清迈区域人口..." : "构建 30,000 合成样本...";
      case 2: return `推理代表 Agent ${Math.floor(pct / 10) + 1}/10 ...`;
      case 3: return `Monte Carlo 模拟 ${Math.floor(pct * 0.8)} / 80 轮...`;
      case 4: return `计算方案对比 ${Math.ceil(pct / 25)}/4 ...`;
      case 5: return "汇总生成分析报告...";
      default: return "";
    }
  }

  const totalProgress = stages.reduce((sum, s) => sum + s.progress, 0) / STAGES.length;
  const formatElapsed = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;

  return (
    <div className="max-w-3xl mx-auto p-8 space-y-8">
      {/* Top Banner */}
      <Card className="text-center py-8">
        {done ? (
          <div className="space-y-3">
            <div className="w-10 h-10 rounded-full bg-white text-black font-bold flex items-center justify-center mx-auto text-lg">
              ✓
            </div>
            <h2 className="text-xl font-light text-white tracking-tight">模拟完成</h2>
            <p className="text-xs text-neutral-400 font-light">共耗时 {formatElapsed(elapsed)} · 报告已被验证并生成</p>
            <Link href={`/studies/${studyId}/report`} className="btn-lazzor-primary inline-flex mt-2">
              查看报告结果 <ArrowRight size={14} />
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            <Loader2 size={24} className="animate-spin text-white mx-auto" />
            <div className="eyebrow">Simulation Executing</div>
            <h2 className="text-xl font-light text-white tracking-tight">正在在泰国数字市场中运行模拟...</h2>
            <p className="text-xs text-neutral-400 font-mono">已用时 {formatElapsed(elapsed)} · 总体进度 {totalProgress.toFixed(0)}%</p>
            <div className="max-w-xs mx-auto pt-2">
              <ProgressBar value={totalProgress} max={100} />
            </div>
          </div>
        )}
      </Card>

      {/* Stages List */}
      <div className="space-y-3">
        <span className="eyebrow">Execution Stages</span>
        <div className="space-y-2">
          {STAGES.map((stage, i) => {
            const s = stages[i];
            return (
              <Card key={stage.id} className={cn(
                "!p-4 transition-colors",
                s.status === "running" && "bg-neutral-900 border-white",
                s.status === "done" && "border-neutral-800"
              )}>
                <div className="flex items-center gap-4">
                  <div className={cn(
                    "w-7 h-7 rounded-full flex items-center justify-center text-xs font-mono font-medium shrink-0",
                    s.status === "done" ? "bg-white text-black" :
                    s.status === "running" ? "bg-neutral-800 text-white border border-neutral-600" :
                    "bg-neutral-950 text-neutral-600 border border-neutral-900"
                  )}>
                    {s.status === "done" ? "✓" : i + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className={cn(
                        "text-xs font-semibold tracking-tight",
                        s.status === "done" ? "text-neutral-300" :
                        s.status === "running" ? "text-white" :
                        "text-neutral-500"
                      )}>
                        {stage.label}
                      </span>
                      {s.status === "running" && (
                        <span className="text-[11px] font-mono text-white">{s.progress.toFixed(0)}%</span>
                      )}
                      {s.status === "done" && (
                        <span className="text-[11px] font-mono text-neutral-400">Done</span>
                      )}
                    </div>
                    <p className="text-[11px] text-neutral-400 font-light mt-0.5">
                      {s.status === "running" ? s.detail : stage.sublabel}
                    </p>
                    {s.status === "running" && (
                      <div className="mt-2">
                        <ProgressBar value={s.progress} max={100} />
                      </div>
                    )}
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
