"use client";

import Link from "next/link";
import { DEMO_CASES, TEMPLATES, STUDY_TYPE_META, PLAN_META } from "@/lib/product-catalog";
import { Card } from "@/components/ui";

const TEMPLATE_GROUPS = ["产品与电商", "定价与广告", "开店与选址", "经营优化"] as const;

export function TemplatesClient() {
  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <h2 className="font-display text-base font-semibold text-primary">选择模板快速开始</h2>
        <p className="text-sm text-muted mt-1">模板预设了常用字段和默认假设，帮助您快速提交第一个项目</p>
      </div>

      <Link href={DEMO_CASES[0].result_href}>
        <Card hover className="border-blue-400/20 bg-blue-500/5">
          <div className="grid sm:grid-cols-[1fr_auto] gap-5 items-center">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-blue-500/10 flex items-center justify-center text-3xl">
                {DEMO_CASES[0].icon}
              </div>
              <div>
                <span className="eyebrow text-blue-300">完整案例 · 无需重新运行</span>
                <h3 className="text-base font-semibold text-white mt-1">{DEMO_CASES[0].label}</h3>
                <p className="text-xs text-neutral-400 mt-1">查看真实保存的 Standard 模拟、数据来源、区间、情景与限制。</p>
              </div>
            </div>
            <span className="btn-cmai-primary">直接查看完整报告 →</span>
          </div>
        </Card>
      </Link>

      {TEMPLATE_GROUPS.map(group => (
        <section key={group} className="space-y-3">
          <div className="flex items-center gap-3">
            <h3 className="text-xs font-semibold text-white">{group}</h3>
            <div className="h-px bg-blue-400/10 flex-1" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 stagger-children">
            {TEMPLATES.filter(template => template.group === group).map(t => {
              const meta = STUDY_TYPE_META[t.study_type];
              const plan = PLAN_META[t.recommended_plan as keyof typeof PLAN_META];
              return (
                <Link
                  key={t.id}
                  href={`/studies/new?template=${t.id}&type=${t.study_type}&category=${t.category}`}
                >
                  <Card hover className="h-full group">
                    <div className="flex items-start gap-3 mb-3">
                      <div
                        className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl shrink-0 transition-smooth group-hover:scale-110"
                        style={{ background: `${meta?.color}18` }}
                      >
                        {t.icon}
                      </div>
                      <div>
                        <h3 className="font-semibold text-primary text-sm group-hover:text-white transition-smooth">
                          {t.label}
                        </h3>
                        <p className="text-xs text-muted mt-0.5">{meta?.label}</p>
                      </div>
                    </div>
                    <p className="text-xs text-secondary line-clamp-2 mb-3">{t.summary}</p>
                    <div className="divider mb-3" />
                    <div className="flex items-center justify-between text-xs text-muted">
                      <div className="flex gap-3">
                        <span>{t.scenarios} 个情景</span>
                        <span>·</span>
                        <span>推荐 {plan.label}</span>
                      </div>
                      <span>⏱ {t.est_time}</span>
                    </div>
                  </Card>
                </Link>
              );
            })}
          </div>
        </section>
      ))}

      {/* Custom */}
      <div className="text-center py-4">
        <p className="text-sm text-muted mb-3">没有合适的模板？</p>
        <Link href="/studies/new" className="btn-secondary">
          自定义新建项目 →
        </Link>
      </div>
    </div>
  );
}
