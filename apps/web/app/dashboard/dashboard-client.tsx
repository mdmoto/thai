"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Plus } from "lucide-react";
import {
  getMeApi,
  listStudiesApi,
  StudyListItem,
  UserProfile,
} from "@/lib/api-client";
import { STUDY_TYPE_META } from "@/lib/product-catalog";
import { Card, EmptyState, PlanBadge, StatusBadge } from "@/components/ui";
import { formatRelativeTime, isRunning, needsAction } from "@/lib/utils";

const QUICK_TEMPLATES = [
  {
    icon: "🐈",
    label: "宠物饮水机样例报告",
    href: "/demo/pet-water",
  },
  {
    icon: "📦",
    label: "通用新品",
    href: "/studies/new?type=PRODUCT_VALIDATION",
  },
  {
    icon: "฿",
    label: "价格测试",
    href: "/studies/new?type=PRICING_STUDY",
  },
];

export function DashboardClient() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [studies, setStudies] = useState<StudyListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getMeApi(), listStudiesApi()])
      .then(([profile, records]) => {
        setUser(profile);
        setStudies(records);
      })
      .catch(err => setError(err instanceof Error ? err.message : "读取工作区失败"))
      .finally(() => setLoading(false));
  }, []);

  const summary = useMemo(
    () => ({
      running: studies.filter(study => isRunning(study.status)).length,
      completed: studies.filter(study => study.status === "COMPLETED").length,
      action: studies.filter(study => needsAction(study.status)).length,
    }),
    [studies],
  );

  if (loading) {
    return <div className="p-8 text-sm text-neutral-400">正在读取您的工作区…</div>;
  }

  if (error || !user) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <Card>
          <span className="eyebrow">Account required</span>
          <h1 className="text-xl font-semibold text-white mt-2">请先登录工作区</h1>
          <p className="text-sm text-neutral-400 mt-2">
            项目、额度和报告均按账号隔离保存。
          </p>
          <Link href="/login" className="btn-cmai-primary mt-5">
            登录或注册 <ArrowRight size={14} />
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-5 sm:p-8 space-y-8 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-6 pb-8 border-b border-neutral-900">
        <div className="max-w-2xl">
          <span className="eyebrow mb-3">Thailand Consumer Decision Lab</span>
          <h1 className="text-3xl sm:text-4xl font-semibold text-white tracking-tight leading-tight">
            先比较泰国市场方案，再决定投入哪一个
          </h1>
          <p className="text-sm text-neutral-400 font-light mt-3 leading-relaxed">
            现已覆盖消费品、定价、线下门店、商圈选址、广告素材与经营情景；结果用于决策筛选，并明确披露未回测部分。
          </p>
        </div>
        <Link href="/studies/new" className="btn-cmai-primary shrink-0">
          <Plus size={15} /> 新建研究项目
        </Link>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="运行中" value={summary.running} />
        <StatCard label="已完成" value={summary.completed} />
        <StatCard label="需要处理" value={summary.action} />
        <StatCard label="可用积分" value={user.credits_balance} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <Card className="xl:col-span-2">
          <div className="flex items-center justify-between mb-5">
            <div>
              <span className="eyebrow">Recent studies</span>
              <h2 className="text-base font-semibold text-white mt-1">最近项目</h2>
            </div>
            <Link href="/studies" className="text-xs text-neutral-400 hover:text-white">
              查看全部
            </Link>
          </div>
          {studies.length === 0 ? (
            <EmptyState
              title="还没有研究项目"
              description="从宠物智能饮水机模板或通用消费品模板开始。"
            />
          ) : (
            <div className="space-y-2">
              {studies.slice(0, 6).map(study => (
                <StudyRow key={study.id} study={study} />
              ))}
            </div>
          )}
        </Card>

        <Card>
          <span className="eyebrow">Quick start</span>
          <h2 className="text-base font-semibold text-white mt-1 mb-4">快速开始</h2>
          <div className="space-y-2">
            {QUICK_TEMPLATES.map(item => (
              <Link
                key={item.label}
                href={item.href}
                className="flex items-center gap-3 rounded-xl border border-neutral-900 bg-black p-3 hover:border-neutral-700 transition-colors"
              >
                <span className="text-lg">{item.icon}</span>
                <span className="text-xs text-neutral-200">{item.label}</span>
                <ArrowRight size={13} className="ml-auto text-neutral-500" />
              </Link>
            ))}
          </div>
          <div className="mt-5 pt-4 border-t border-neutral-900 text-[11px] text-neutral-500 leading-relaxed">
            宠物饮水机模板已连接公开竞品价格面板；其他品类使用通用消费品先验并在报告中标注。
          </div>
        </Card>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <Card className="!p-4">
      <div className="text-2xl font-semibold text-white tabular-nums">{value}</div>
      <div className="text-[11px] text-neutral-500 mt-1">{label}</div>
    </Card>
  );
}

function StudyRow({ study }: { study: StudyListItem }) {
  const meta =
    STUDY_TYPE_META[study.study_type as keyof typeof STUDY_TYPE_META];
  const href =
    study.status === "COMPLETED"
      ? `/studies/report?id=${encodeURIComponent(study.id)}`
      : `/studies/view?id=${encodeURIComponent(study.id)}`;
  return (
    <Link
      href={href}
      className="flex items-center gap-3 rounded-xl border border-neutral-900 bg-black p-3 hover:border-neutral-700 transition-colors"
    >
      <div className="w-9 h-9 rounded-lg bg-neutral-900 flex items-center justify-center">
        {meta?.icon || "📦"}
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-xs text-white truncate">{study.name}</div>
        <div className="text-[10px] text-neutral-500 mt-1">
          {formatRelativeTime(study.updated_at)}
        </div>
      </div>
      <StatusBadge status={study.status as Parameters<typeof StatusBadge>[0]["status"]} />
      <PlanBadge plan={study.plan_code as Parameters<typeof PlanBadge>[0]["plan"]} />
    </Link>
  );
}
