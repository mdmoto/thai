"use client";

import Link from "next/link";
import { TEMPLATES, STUDY_TYPE_META, PLAN_META } from "@/lib/product-catalog";
import { Card } from "@/components/ui";

export function TemplatesClient() {
  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <h2 className="font-display text-base font-semibold text-primary">选择模板快速开始</h2>
        <p className="text-sm text-muted mt-1">模板预设了常用字段和默认假设，帮助您快速提交第一个项目</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 stagger-children">
        {TEMPLATES.map(t => {
          const meta = STUDY_TYPE_META[t.study_type];
          const plan = PLAN_META[t.recommended_plan as keyof typeof PLAN_META];
          return (
            <Link
              key={t.id}
              href={"result_href" in t
                ? t.result_href
                : `/studies/new?template=${t.id}&type=${t.study_type}&category=${t.category}`}
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
                <p className="text-xs text-secondary line-clamp-2 mb-3">{meta?.desc}</p>
                <div className="divider mb-3" />
                <div className="flex items-center justify-between text-xs text-muted">
                  <div className="flex gap-3">
                    <span>{"result_href" in t ? "完整样例报告" : `${t.scenarios} 个情景`}</span>
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
