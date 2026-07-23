"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { CheckCircle2, Clock, Loader2, AlertCircle, Bell } from "lucide-react";
import { Card, ProgressBar } from "@/components/ui";
import { cn } from "@/lib/utils";

interface Stage {
  id: string;
  label: string;
  sublabel: string;
  icon: string;
  durationMs: number;
}

const STAGES: Stage[] = [
  { id: "parsing",    label: "资料解析",       sublabel: "分析上传内容，提取结构化信息",   icon: "📄", durationMs: 4000 },
  { id: "population", label: "目标人口构建",   sublabel: "从泰国合成人口中筛选目标群体",   icon: "👥", durationMs: 6000 },
  { id: "agents",     label: "代表消费者推理", sublabel: "AI 消费者对方案产生结构化反应",   icon: "🤖", durationMs: 8000 },
  { id: "simulation", label: "群体模拟",       sublabel: "Monte Carlo 80 轮大规模行为模拟", icon: "⚡", durationMs: 12000 },
  { id: "scenarios",  label: "情景对比",       sublabel: "比较 4 个方案的结果差异",         icon: "🔀", durationMs: 6000 },
  { id: "report",     label: "报告生成",       sublabel: "整合结果，生成可追溯报告",        icon: "📊", durationMs: 4000 },
];

type StageStatus = "waiting" | "running" | "done";

interface StageState {
  status: StageStatus;
  progress: number; // 0-100
  detail: string;
}

export function RunProgressClient({ studyId }: { studyId: string }) {
  const [stages, setStages] = useState<StageState[]>(
    STAGES.map(() => ({ status: "waiting", progress: 0, detail: "" }))
  );
  const [currentStage, setCurrentStage] = useState(0);
  const [done, setDone] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  // Simulate progress
  useEffect(() => {
    if (done) return;

    const timer = setInterval(() => {
      setElapsed(e => e + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [done]);

  useEffect(() => {
    if (done) return;
    if (currentStage >= STAGES.length) {
      setDone(true);
      return;
    }

    const stage = STAGES[currentStage];
    const startTime = Date.now();
    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const pct = Math.min(99, (elapsed / stage.durationMs) * 100);

      setStages(prev => {
        const next = [...prev];
        next[currentStage] = {
          status: "running",
          progress: pct,
          detail: getStageDetail(currentStage, pct),
        };
        return next;
      });

      if (elapsed >= stage.durationMs) {
        clearInterval(interval);
        setStages(prev => {
          const next = [...prev];
          next[currentStage] = { status: "done", progress: 100, detail: "完成" };
          return next;
        });
        setCurrentStage(s => s + 1);
      }
    }, 100);

    return () => clearInterval(interval);
  }, [currentStage, done]);

  function getStageDetail(stageIdx: number, pct: number): string {
    switch (stageIdx) {
      case 0: return pct < 50 ? "解析文本和图片..." : "提取产品参数...";
      case 1: return pct < 50 ? "筛选目标地区人口..." : "生成 30,000 人合成群体...";
      case 2: return `推理代表消费者 ${Math.floor(pct / 10) + 1}/10 ...`;
      case 3: return `Monte Carlo 第 ${Math.floor(pct * 0.8)} / 80 轮...`;
      case 4: return `情景对比 ${Math.ceil(pct / 25)}/4 ...`;
      case 5: return pct < 60 ? "生成图表..." : "生成叙述报告...";
      default: return "";
    }
  }

  const totalProgress = stages.reduce((sum, s) => sum + s.progress, 0) / STAGES.length;
  const formatElapsed = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6 animate-fade-in-up">
      {/* Header status */}
      <Card className={cn(
        "relative overflow-hidden",
        done && "border-emerald-500/50"
      )}>
        <div className="absolute inset-0 opacity-5"
          style={{ background: done ? "radial-gradient(circle at 50% 0%, #22C55E, transparent 60%)" : "radial-gradient(circle at 50% 0%, #8B5CF6, transparent 60%)" }} />
        <div className="relative text-center py-4">
          {done ? (
            <>
              <CheckCircle2 size={40} className="text-emerald-400 mx-auto mb-3" />
              <h2 className="text-xl font-bold text-primary">模拟完成！</h2>
              <p className="text-sm text-secondary mt-1">共耗时 {formatElapsed(elapsed)}，报告已就绪</p>
              <Link href={`/studies/${studyId}/report`} className="btn-primary mt-4 inline-flex">
                查看报告 →
              </Link>
            </>
          ) : (
            <>
              <div className="flex items-center justify-center gap-2 mb-3">
                <Loader2 size={24} className="text-violet-400 animate-spin" />
                <span className="text-violet-400 font-medium text-sm">运行中</span>
              </div>
              <h2 className="text-xl font-bold text-primary">正在模拟泰国市场...</h2>
              <p className="text-sm text-secondary mt-1">
                已运行 {formatElapsed(elapsed)} · 总进度 {totalProgress.toFixed(0)}%
              </p>
              <div className="mt-4 max-w-xs mx-auto">
                <ProgressBar value={totalProgress} max={100} />
              </div>
            </>
          )}
        </div>
      </Card>

      {/* Notification banner */}
      {!done && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)]">
          <Bell size={16} className="text-muted shrink-0" />
          <p className="text-xs text-secondary">
            可关闭此页面，模拟完成后将通过站内通知和邮件提醒您。
          </p>
        </div>
      )}

      {/* Stage list */}
      <div className="space-y-2">
        <span className="section-heading">运行阶段</span>
        <div className="space-y-2 stagger-children">
          {STAGES.map((stage, i) => {
            const s = stages[i];
            return (
              <Card key={stage.id} className={cn(
                "!p-4 transition-smooth",
                s.status === "running" && "border-violet-500/30 bg-violet-500/5",
                s.status === "done" && "border-emerald-500/20"
              )}>
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center text-base shrink-0",
                    s.status === "done" ? "bg-emerald-500/20" :
                    s.status === "running" ? "bg-violet-500/20" :
                    "bg-[var(--color-bg-base)]"
                  )}>
                    {s.status === "done" ? (
                      <CheckCircle2 size={16} className="text-emerald-400" />
                    ) : s.status === "running" ? (
                      <Loader2 size={16} className="text-violet-400 animate-spin" />
                    ) : (
                      <Clock size={16} className="text-muted" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        "text-sm font-medium",
                        s.status === "done" ? "text-emerald-400" :
                        s.status === "running" ? "text-primary" :
                        "text-muted"
                      )}>
                        {stage.label}
                      </span>
                      {s.status === "running" && s.progress > 0 && (
                        <span className="text-xs text-violet-400 ml-auto">
                          {s.progress.toFixed(0)}%
                        </span>
                      )}
                      {s.status === "done" && (
                        <span className="text-xs text-emerald-400 ml-auto">100%</span>
                      )}
                    </div>
                    <p className="text-xs text-muted mt-0.5">
                      {s.status === "running" ? s.detail : s.status === "done" ? "✓ 完成" : stage.sublabel}
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

      {/* Technical details */}
      <Card className="bg-[var(--color-bg-base)]">
        <span className="section-heading">技术信息</span>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <TechRow label="模拟规模" value="30,000 人" />
          <TechRow label="Monte Carlo" value="80 轮" />
          <TechRow label="情景数" value="4 个" />
          <TechRow label="World Model" value="TH-2026.07.1" />
          <TechRow label="Run ID" value={`run_${studyId.slice(-8)}`} />
          <TechRow label="随机种子" value="0x4A2F8B" />
        </div>
      </Card>
    </div>
  );
}

function TechRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-1 border-b border-[var(--color-border-subtle)] last:border-0">
      <span className="text-muted">{label}</span>
      <span className="text-secondary font-mono">{value}</span>
    </div>
  );
}
