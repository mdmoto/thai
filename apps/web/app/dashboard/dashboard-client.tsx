"use client";

import Link from "next/link";
import { useState } from "react";
import {
  TrendingUp, AlertCircle, CheckCircle2, Clock,
  ArrowRight, Zap, BarChart3, Users, Globe,
} from "lucide-react";
import { MOCK_STUDIES, MOCK_ORG, MOCK_USAGE, PLAN_META, STUDY_TYPE_META } from "@/lib/mock-data";
import { StatusBadge, PlanBadge, Card, EmptyState } from "@/components/ui";
import { formatRelativeTime, isRunning, needsAction } from "@/lib/utils";

const running = MOCK_STUDIES.filter(s => isRunning(s.status));
const completed = MOCK_STUDIES.filter(s => s.status === "COMPLETED");
const actionRequired = MOCK_STUDIES.filter(s => needsAction(s.status));

const QUICK_TEMPLATES = [
  { icon: "📦", label: "产品测试", href: "/studies/new?type=PRODUCT_VALIDATION" },
  { icon: "🍜", label: "餐厅评估", href: "/studies/new?type=RESTAURANT" },
  { icon: "☕", label: "咖啡馆", href: "/studies/new?type=CAFE" },
  { icon: "🍺", label: "酒吧", href: "/studies/new?type=BAR" },
  { icon: "💰", label: "定价测试", href: "/studies/new?type=PRICING_STUDY" },
  { icon: "📍", label: "选址对比", href: "/studies/new?type=SITE_COMPARISON" },
];

export function DashboardClient() {
  const plan = PLAN_META[MOCK_ORG.plan_code as keyof typeof PLAN_META];

  return (
    <div className="p-6 space-y-6 animate-fade-in-up">
      {/* Welcome banner */}
      <div className="glass-card p-6 relative overflow-hidden">
        <div className="absolute inset-0 opacity-5"
          style={{ background: "radial-gradient(circle at 80% 50%, #D4A853 0%, transparent 60%)" }} />
        <div className="relative flex items-start justify-between">
          <div>
            <p className="text-sm text-muted mb-1">欢迎回来</p>
            <h2 className="text-2xl font-bold text-primary mb-2">
              <span className="text-gradient-gold">Thailand</span> Market Twin
            </h2>
            <p className="text-sm text-secondary max-w-md">
              把产品或门店方案放入泰国合成消费者市场，<br />
              在投入之前发现风险，比较方案。
            </p>
          </div>
          <div className="hidden sm:flex flex-col items-end gap-2">
            <div className="glass-card px-4 py-2 text-center">
              <div className="text-2xl font-bold text-gradient-gold">{MOCK_ORG.credits_balance}</div>
              <div className="text-xs text-muted">剩余额度</div>
            </div>
            <span className="text-xs text-muted">{plan?.label} 套餐</span>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-3">
          <Link href="/studies/new" className="btn-primary">
            <Zap size={15} /> 新建项目
          </Link>
          <Link href="/templates" className="btn-secondary">
            <BarChart3 size={15} /> 浏览模板
          </Link>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 stagger-children">
        <StatCard
          label="运行中"
          value={running.length}
          icon={<Clock size={18} className="text-violet-400" />}
          color="text-violet-400"
          href="/studies?status=running"
        />
        <StatCard
          label="已完成"
          value={completed.length}
          icon={<CheckCircle2 size={18} className="text-emerald-400" />}
          color="text-emerald-400"
          href="/studies?status=completed"
        />
        <StatCard
          label="待处理"
          value={actionRequired.length}
          icon={<AlertCircle size={18} className="text-amber-400" />}
          color="text-amber-400"
          href="/studies?status=action"
          alert={actionRequired.length > 0}
        />
        <StatCard
          label="剩余额度"
          value={MOCK_ORG.credits_balance}
          icon={<TrendingUp size={18} className="text-[var(--color-gold)]" />}
          color="text-[var(--color-gold)]"
          href="/billing"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent studies */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <span className="section-heading">最近项目</span>
            <Link href="/studies" className="text-xs text-gold hover:text-gold-light transition-smooth flex items-center gap-1">
              查看全部 <ArrowRight size={12} />
            </Link>
          </div>

          {MOCK_STUDIES.length === 0 ? (
            <Card>
              <EmptyState
                icon="📊"
                title="还没有项目"
                description="新建一个项目，把您的产品或门店放入泰国消费者市场测试"
                action={
                  <Link href="/studies/new" className="btn-primary text-sm">
                    新建第一个项目
                  </Link>
                }
              />
            </Card>
          ) : (
            <div className="space-y-2 stagger-children">
              {MOCK_STUDIES.slice(0, 5).map(study => (
                <StudyRow key={study.id} study={study} />
              ))}
            </div>
          )}
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {/* Quick templates */}
          <div className="space-y-3">
            <span className="section-heading">快速开始</span>
            <div className="grid grid-cols-2 gap-2 stagger-children">
              {QUICK_TEMPLATES.map(t => (
                <Link
                  key={t.label}
                  href={t.href}
                  className="glass-card p-3 flex flex-col items-center gap-1.5 hover:border-[var(--color-gold-dim)] transition-smooth cursor-pointer text-center"
                >
                  <span className="text-xl">{t.icon}</span>
                  <span className="text-xs font-medium text-secondary">{t.label}</span>
                </Link>
              ))}
            </div>
          </div>

          {/* Platform info */}
          <Card>
            <div className="space-y-3">
              <span className="section-heading">平台说明</span>
              <InfoRow icon={<Users size={14} />} text="使用合成人口，非真实自然人" />
              <InfoRow icon={<Globe size={14} />} text="结果适合比较方案、发现风险" />
              <InfoRow icon={<BarChart3 size={14} />} text="不保证实际销量或投资回报" />
              <div className="divider mt-2" />
              <p className="text-xs text-muted leading-relaxed">
                客户输入越完整，结果越有参考价值。所有数字均可追溯至模拟任务和数据版本。
              </p>
            </div>
          </Card>

          {/* Usage mini chart */}
          <Card>
            <div className="space-y-3">
              <span className="section-heading">本周使用</span>
              <div className="flex items-end gap-1 h-16">
                {MOCK_USAGE.map((d, i) => (
                  <div key={i} className="flex-1 flex flex-col items-center gap-1">
                    <div
                      className="w-full rounded-t-sm transition-all"
                      style={{
                        height: `${d.runs > 0 ? (d.runs / 3) * 100 : 4}%`,
                        background: d.runs > 0
                          ? "linear-gradient(to top, var(--color-gold-dim), var(--color-gold))"
                          : "var(--color-border)",
                        minHeight: "4px",
                      }}
                    />
                    <span className="text-[9px] text-muted">{d.date.slice(3)}</span>
                  </div>
                ))}
              </div>
              <div className="text-xs text-secondary">
                本周共运行 <span className="text-gold font-medium">{MOCK_USAGE.reduce((s, d) => s + d.runs, 0)}</span> 次模拟
              </div>
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
  label, value, icon, color, href, alert,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  color: string;
  href: string;
  alert?: boolean;
}) {
  return (
    <Link href={href}>
      <Card hover className="relative">
        {alert && value > 0 && (
          <span className="absolute top-3 right-3 w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
        )}
        <div className="flex items-center gap-3 mb-3">
          <div className="p-2 rounded-lg bg-[var(--color-bg-base)]">{icon}</div>
        </div>
        <div className={`text-2xl font-bold ${color}`}>{value}</div>
        <div className="text-xs text-muted mt-1">{label}</div>
      </Card>
    </Link>
  );
}

function StudyRow({ study }: { study: typeof MOCK_STUDIES[0] }) {
  const meta = STUDY_TYPE_META[study.study_type];
  return (
    <Link href={`/studies/${study.id}`}>
      <Card hover className="!p-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 text-lg"
            style={{ background: `${meta?.color}18` }}>
            {meta?.icon}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <StatusBadge status={study.status as Parameters<typeof StatusBadge>[0]["status"]} />
              <PlanBadge plan={study.plan_code as Parameters<typeof PlanBadge>[0]["plan"]} />
            </div>
            <p className="text-sm font-medium text-primary truncate">{study.name}</p>
            <p className="text-xs text-muted mt-0.5">{formatRelativeTime(study.updated_at)}</p>
          </div>
          <ArrowRight size={16} className="text-muted shrink-0" />
        </div>
      </Card>
    </Link>
  );
}

function InfoRow({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-start gap-2 text-xs text-secondary">
      <span className="text-muted mt-0.5">{icon}</span>
      <span>{text}</span>
    </div>
  );
}
