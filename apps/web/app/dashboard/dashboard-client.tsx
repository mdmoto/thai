"use client";

import Link from "next/link";
import {
  ArrowRight, Plus, ArrowUpRight,
} from "lucide-react";
import { MOCK_STUDIES, MOCK_ORG, MOCK_USAGE, PLAN_META, STUDY_TYPE_META } from "@/lib/mock-data";
import { StatusBadge, PlanBadge, Card, EmptyState, CountUp } from "@/components/ui";
import { formatRelativeTime, isRunning, needsAction } from "@/lib/utils";

const running = MOCK_STUDIES.filter(s => isRunning(s.status));
const completed = MOCK_STUDIES.filter(s => s.status === "COMPLETED");
const actionRequired = MOCK_STUDIES.filter(s => needsAction(s.status));

const QUICK_TEMPLATES = [
  { icon: "📦", label: "产品验证", href: "/studies/new?type=PRODUCT_VALIDATION" },
  { icon: "🍜", label: "餐厅评估", href: "/studies/new?type=RESTAURANT" },
  { icon: "☕", label: "咖啡馆", href: "/studies/new?type=CAFE" },
  { icon: "🍺", label: "酒吧方案", href: "/studies/new?type=BAR" },
  { icon: "💰", label: "定价测试", href: "/studies/new?type=PRICING_STUDY" },
  { icon: "📍", label: "选址对比", href: "/studies/new?type=SITE_COMPARISON" },
];

export function DashboardClient() {
  const plan = PLAN_META[MOCK_ORG.plan_code as keyof typeof PLAN_META];

  return (
    <div className="p-8 space-y-10 max-w-7xl mx-auto">
      {/* Hero */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-6 pb-8 border-b border-neutral-900">
        <div className="max-w-xl">
          <span className="eyebrow mb-3">Thailand Digital Market Twin</span>
          <h1 className="text-3xl sm:text-4xl font-semibold text-white tracking-tight leading-tight">
            把决策放进泰国真实市场里，先看结果，再花预算
          </h1>
          <p className="text-sm text-neutral-400 font-light mt-3 leading-relaxed">
            基于合成泰国消费者人口，模拟产品、门店与定价方案的市场反应。
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <Link href="/studies/new" className="btn-cmai-primary">
            <Plus size={15} /> 新建研究项目
          </Link>
          <Link href="/templates" className="btn-cmai-secondary">
            浏览模板
          </Link>
        </div>
      </div>

      {/* ── Stats row ─────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
        <StatCard
          eyebrow="Running"
          label="运行中任务"
          value={running.length}
          href="/studies?status=running"
        />
        <StatCard
          eyebrow="Completed"
          label="已完成模拟"
          value={completed.length}
          href="/studies?status=completed"
          accent="jade"
        />
        <StatCard
          eyebrow="Action"
          label="待确认 / 处理"
          value={actionRequired.length}
          href="/studies?status=action"
          alert={actionRequired.length > 0}
          accent="clay"
        />
        <StatCard
          eyebrow="Credits"
          label="剩余运行额度"
          value={MOCK_ORG.credits_balance}
          href="/billing"
          badge={plan?.label}
        />
      </div>

      {/* ── Main Grid Layout ──────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left 8 cols: Recent studies */}
        <div className="lg:col-span-8 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white tracking-tight">最近研究项目</h2>
            <Link href="/studies" className="text-xs text-neutral-400 hover:text-white transition-colors flex items-center gap-1 font-light">
              查看全部 <ArrowRight size={12} />
            </Link>
          </div>

          {MOCK_STUDIES.length === 0 ? (
            <Card>
              <EmptyState
                title="还没有研究项目"
                description="新建一个项目，把您的产品或门店放入泰国消费者市场跑模拟"
                action={
                  <Link href="/studies/new" className="btn-lazzor-primary text-xs mt-2">
                    新建第一个项目
                  </Link>
                }
              />
            </Card>
          ) : (
            <div className="space-y-3">
              {MOCK_STUDIES.slice(0, 5).map(study => (
                <StudyRow key={study.id} study={study} />
              ))}
            </div>
          )}
        </div>

        {/* Right 4 cols: Quick Start & Platform Info */}
        <div className="lg:col-span-4 space-y-6">
          {/* Quick templates */}
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-white tracking-tight">快速模版入口</h2>
            <div className="grid grid-cols-2 gap-3">
              {QUICK_TEMPLATES.map(t => (
                <Link
                  key={t.label}
                  href={t.href}
                  className="card-lazzor p-4 flex flex-col items-start gap-2 hover:bg-[#171717] transition-colors group"
                >
                  <span className="text-xl">{t.icon}</span>
                  <div className="flex items-center justify-between w-full">
                    <span className="text-xs font-medium text-neutral-200 group-hover:text-white">{t.label}</span>
                    <ArrowUpRight size={12} className="text-neutral-500 group-hover:text-neutral-300 transition-colors" />
                  </div>
                </Link>
              ))}
            </div>
          </div>

          {/* Usage Chart */}
          <Card>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="eyebrow">Usage</span>
                <span className="text-xs text-neutral-400 font-light">本周共 {MOCK_USAGE.reduce((s, d) => s + d.runs, 0)} 次</span>
              </div>
              <div className="flex items-end gap-2 h-20 pt-2">
                {MOCK_USAGE.map((d, i) => (
                  <div key={i} className="flex-1 flex flex-col items-center gap-1.5 h-full justify-end">
                    <div
                      className="w-full rounded-t bg-neutral-200 transition-all"
                      style={{
                        height: `${d.runs > 0 ? (d.runs / 3) * 100 : 8}%`,
                        opacity: d.runs > 0 ? 0.85 : 0.12,
                      }}
                    />
                    <span className="text-[10px] text-neutral-500 font-mono">{d.date.slice(3)}</span>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          {/* Platform Standards */}
          <Card>
            <div className="space-y-3">
              <span className="eyebrow">Platform Assurance</span>
              <h3 className="text-xs font-semibold text-white">严谨的数据与模型约束</h3>
              <p className="text-xs text-neutral-400 font-light leading-relaxed">
                平台基于 Thailand World Model 合成人口计算。不自由编造数字，所有报告结果均能追溯至对应的运行 ID 与数据版本。
              </p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────
// Sub components
// ─────────────────────────────────────────
function StatCard({
  eyebrow, label, value, href, alert, badge, accent,
}: {
  eyebrow: string;
  label: string;
  value: number;
  href: string;
  alert?: boolean;
  badge?: string;
  accent?: "jade" | "gold" | "clay";
}) {
  return (
    <Link href={href}>
      <Card hover accent={accent} className="group">
        <div className="flex items-center justify-between mb-3">
          <span className="eyebrow">{eyebrow}</span>
          {alert && <span className="w-1.5 h-1.5 rounded-full bg-[#C15C4A]" />}
          {badge && <span className="text-[10px] font-mono text-neutral-400">{badge}</span>}
        </div>
        <div className="text-3xl sm:text-4xl font-semibold text-white tracking-tight">
          <CountUp value={value} />
        </div>
        <div className="text-xs text-neutral-400 font-light mt-1 flex items-center justify-between">
          <span>{label}</span>
          <ArrowRight size={13} className="opacity-0 group-hover:opacity-100 transition-opacity text-white" />
        </div>
      </Card>
    </Link>
  );
}

function StudyRow({ study }: { study: typeof MOCK_STUDIES[0] }) {
  const meta = STUDY_TYPE_META[study.study_type];
  return (
    <Link href={`/studies/${study.id}`}>
      <Card hover className="!p-4">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-neutral-900 border border-neutral-800 flex items-center justify-center text-lg shrink-0">
            {meta?.icon}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <StatusBadge status={study.status as Parameters<typeof StatusBadge>[0]["status"]} />
              <PlanBadge plan={study.plan_code as Parameters<typeof PlanBadge>[0]["plan"]} />
            </div>
            <p className="text-xs font-medium text-white truncate">{study.name}</p>
          </div>
          <div className="hidden sm:flex flex-col items-end gap-1 shrink-0">
            <span className="text-[11px] text-neutral-500 font-light">{formatRelativeTime(study.updated_at)}</span>
            <ArrowUpRight size={14} className="text-neutral-500 group-hover:text-white transition-colors" />
          </div>
        </div>
      </Card>
    </Link>
  );
}
