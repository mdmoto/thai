"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowUpRight, LayoutGrid, List, Search } from "lucide-react";
import { listStudiesApi, StudyListItem } from "@/lib/api-client";
import { STUDY_TYPE_META } from "@/lib/product-catalog";
import { Card, EmptyState, PlanBadge, StatusBadge } from "@/components/ui";
import { formatRelativeTime } from "@/lib/utils";

const STATUS_FILTERS = [
  { label: "全部", value: "" },
  { label: "已完成", value: "COMPLETED" },
  { label: "待运行", value: "READY" },
  { label: "失败可重试", value: "FAILED_RECOVERABLE" },
];

export function StudiesClient() {
  const [studies, setStudies] = useState<StudyListItem[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [view, setView] = useState<"list" | "grid">("list");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listStudiesApi()
      .then(setStudies)
      .catch(err => setError(err instanceof Error ? err.message : "读取项目失败"))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(
    () =>
      studies.filter(study => {
        const matchesSearch = study.name
          .toLowerCase()
          .includes(search.toLowerCase());
        const matchesStatus =
          !statusFilter || study.status === statusFilter;
        return matchesSearch && matchesStatus;
      }),
    [search, statusFilter, studies],
  );

  if (loading) {
    return <div className="p-8 text-sm text-neutral-400">正在读取项目…</div>;
  }

  return (
    <div className="p-5 sm:p-8 space-y-6 max-w-7xl mx-auto">
      {error && (
        <Card>
          <p className="text-sm text-rose-300">{error}</p>
          <Link href="/login" className="btn-cmai-primary mt-4">登录工作区</Link>
        </Card>
      )}
      {!error && (
        <>
          <div className="flex flex-col lg:flex-row gap-3">
            <div className="relative flex-1">
              <Search
                size={15}
                className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500"
              />
              <input
                type="search"
                placeholder="搜索项目名称…"
                value={search}
                onChange={event => setSearch(event.target.value)}
                className="input-lazzor pl-10"
              />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {STATUS_FILTERS.map(filter => (
                <button
                  key={filter.value}
                  onClick={() => setStatusFilter(filter.value)}
                  className={`px-3 py-2 rounded-full text-xs transition-colors ${
                    statusFilter === filter.value
                      ? "bg-white text-black"
                      : "bg-neutral-900 text-neutral-400 hover:text-white"
                  }`}
                >
                  {filter.label}
                </button>
              ))}
              <div className="flex items-center bg-neutral-900 rounded-full p-1">
                <button
                  aria-label="列表视图"
                  onClick={() => setView("list")}
                  className={`p-1.5 rounded-full ${view === "list" ? "bg-neutral-700 text-white" : "text-neutral-500"}`}
                >
                  <List size={14} />
                </button>
                <button
                  aria-label="网格视图"
                  onClick={() => setView("grid")}
                  className={`p-1.5 rounded-full ${view === "grid" ? "bg-neutral-700 text-white" : "text-neutral-500"}`}
                >
                  <LayoutGrid size={14} />
                </button>
              </div>
            </div>
          </div>

          <p className="text-xs text-neutral-400">
            共 <span className="text-white">{filtered.length}</span> 个项目
          </p>

          {filtered.length === 0 ? (
            <Card>
              <EmptyState
                title="没有匹配项目"
                description={
                  studies.length
                    ? "请修改搜索或筛选条件。"
                    : "创建第一个消费品研究项目。"
                }
              />
              {!studies.length && (
                <div className="text-center">
                  <Link href="/studies/new" className="btn-cmai-primary mt-3">
                    新建项目
                  </Link>
                </div>
              )}
            </Card>
          ) : view === "list" ? (
            <div className="space-y-3">
              {filtered.map(study => (
                <StudyListRow key={study.id} study={study} />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
              {filtered.map(study => (
                <StudyGridCard key={study.id} study={study} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function studyHref(study: StudyListItem) {
  return study.status === "COMPLETED"
    ? `/studies/report?id=${encodeURIComponent(study.id)}`
    : `/studies/view?id=${encodeURIComponent(study.id)}`;
}

function StudyListRow({ study }: { study: StudyListItem }) {
  const meta =
    STUDY_TYPE_META[study.study_type as keyof typeof STUDY_TYPE_META];
  return (
    <Link href={studyHref(study)}>
      <Card hover className="!p-4">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-neutral-900 flex items-center justify-center text-lg shrink-0">
            {meta?.icon || "📦"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <StatusBadge status={study.status as Parameters<typeof StatusBadge>[0]["status"]} />
              <PlanBadge plan={study.plan_code as Parameters<typeof PlanBadge>[0]["plan"]} />
              <span className="text-xs text-neutral-500">{meta?.label}</span>
            </div>
            <p className="text-xs font-medium text-white truncate">{study.name}</p>
          </div>
          <span className="hidden sm:block text-xs text-neutral-500">
            {formatRelativeTime(study.updated_at)}
          </span>
          <ArrowUpRight size={14} className="text-neutral-500" />
        </div>
      </Card>
    </Link>
  );
}

function StudyGridCard({ study }: { study: StudyListItem }) {
  const meta =
    STUDY_TYPE_META[study.study_type as keyof typeof STUDY_TYPE_META];
  return (
    <Link href={studyHref(study)}>
      <Card hover className="h-full">
        <div className="flex items-center justify-between mb-4">
          <div className="w-10 h-10 rounded-xl bg-neutral-900 flex items-center justify-center text-lg">
            {meta?.icon || "📦"}
          </div>
          <StatusBadge status={study.status as Parameters<typeof StatusBadge>[0]["status"]} />
        </div>
        <h3 className="font-medium text-white text-sm mb-5">{study.name}</h3>
        <div className="flex items-center justify-between pt-3 border-t border-neutral-900">
          <PlanBadge plan={study.plan_code as Parameters<typeof PlanBadge>[0]["plan"]} />
          <span className="text-[11px] text-neutral-500">
            {formatRelativeTime(study.updated_at)}
          </span>
        </div>
      </Card>
    </Link>
  );
}
