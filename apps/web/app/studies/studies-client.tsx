"use client";

import Link from "next/link";
import { useState } from "react";
import { Search, ArrowUpRight, LayoutGrid, List } from "lucide-react";
import { MOCK_STUDIES, STUDY_TYPE_META } from "@/lib/mock-data";
import { StatusBadge, PlanBadge, Card, EmptyState } from "@/components/ui";
import { formatRelativeTime } from "@/lib/utils";

const STATUS_FILTERS = [
  { label: "全部", value: "" },
  { label: "运行中", value: "running" },
  { label: "已完成", value: "COMPLETED" },
  { label: "待确认", value: "NEEDS_CONFIRMATION" },
  { label: "草稿", value: "DRAFT" },
  { label: "失败", value: "failed" },
];

const RUNNING_STATUSES = ["PARSING","QUEUED","PREPARING_POPULATION","RUNNING_AGENTS","RUNNING_SIMULATION","RUNNING_SCENARIOS","GENERATING_REPORT","RETRYING"];
const FAILED_STATUSES = ["FAILED_FINAL","FAILED_RECOVERABLE"];

function matchesFilter(status: string, filter: string) {
  if (!filter) return true;
  if (filter === "running") return RUNNING_STATUSES.includes(status);
  if (filter === "failed") return FAILED_STATUSES.includes(status);
  return status === filter;
}

export function StudiesClient() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [view, setView] = useState<"list" | "grid">("list");

  const filtered = MOCK_STUDIES.filter(s => {
    const matchSearch = s.name.toLowerCase().includes(search.toLowerCase());
    const matchStatus = matchesFilter(s.status, statusFilter);
    return matchSearch && matchStatus;
  });

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      {/* Controls */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500" />
          <input
            type="text"
            placeholder="搜索项目名称..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="input-lazzor pl-10"
          />
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-neutral-900 border border-neutral-800 rounded-full p-1">
            {STATUS_FILTERS.map(f => (
              <button
                key={f.value}
                onClick={() => setStatusFilter(f.value)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                  statusFilter === f.value
                    ? "bg-white text-black font-semibold"
                    : "text-neutral-400 hover:text-white"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1 bg-neutral-900 border border-neutral-800 rounded-full p-1">
            <button
              onClick={() => setView("list")}
              className={`p-1.5 rounded-full transition-colors ${view === "list" ? "bg-neutral-800 text-white" : "text-neutral-500"}`}
            >
              <List size={14} />
            </button>
            <button
              onClick={() => setView("grid")}
              className={`p-1.5 rounded-full transition-colors ${view === "grid" ? "bg-neutral-800 text-white" : "text-neutral-500"}`}
            >
              <LayoutGrid size={14} />
            </button>
          </div>
        </div>
      </div>

      <p className="text-xs text-neutral-400 font-light">
        共 <span className="text-white font-medium">{filtered.length}</span> 个研究项目
      </p>

      {/* Studies grid/list */}
      {filtered.length === 0 ? (
        <Card>
          <EmptyState
            title="没有找到匹配的项目"
            description="尝试修改搜索词或筛选条件"
          />
        </Card>
      ) : view === "list" ? (
        <div className="space-y-3">
          {filtered.map(study => (
            <StudyListItem key={study.id} study={study} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map(study => (
            <StudyGridCard key={study.id} study={study} />
          ))}
        </div>
      )}
    </div>
  );
}

function StudyListItem({ study }: { study: typeof MOCK_STUDIES[0] }) {
  const meta = STUDY_TYPE_META[study.study_type];
  return (
    <Link href={`/studies/${study.id}`}>
      <Card hover className="!p-4">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-neutral-900 border border-neutral-800 flex items-center justify-center text-lg shrink-0" style={{ boxShadow: meta?.color ? `inset 0 0 0 1px ${meta.color}22` : undefined }}>
            {meta?.icon}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <StatusBadge status={study.status as Parameters<typeof StatusBadge>[0]["status"]} />
              <PlanBadge plan={study.plan_code as Parameters<typeof PlanBadge>[0]["plan"]} />
              <span className="text-xs text-neutral-500 font-light">{meta?.label}</span>
            </div>
            <p className="text-xs font-medium text-white truncate">{study.name}</p>
          </div>
          <div className="hidden sm:flex items-center gap-3 shrink-0">
            <span className="text-xs text-neutral-500 font-light">{formatRelativeTime(study.updated_at)}</span>
            <ArrowUpRight size={14} className="text-neutral-500 group-hover:text-white transition-colors" />
          </div>
        </div>
      </Card>
    </Link>
  );
}

function StudyGridCard({ study }: { study: typeof MOCK_STUDIES[0] }) {
  const meta = STUDY_TYPE_META[study.study_type];
  return (
    <Link href={`/studies/${study.id}`}>
      <Card hover className="h-full flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between mb-3">
            <div className="w-10 h-10 rounded-xl bg-neutral-900 border border-neutral-800 flex items-center justify-center text-lg">
              {meta?.icon}
            </div>
            <StatusBadge status={study.status as Parameters<typeof StatusBadge>[0]["status"]} />
          </div>
          <h3 className="font-medium text-white text-xs mb-3 line-clamp-2">{study.name}</h3>
        </div>
        <div className="flex items-center justify-between pt-3 border-t border-neutral-900">
          <PlanBadge plan={study.plan_code as Parameters<typeof PlanBadge>[0]["plan"]} />
          <span className="text-[11px] text-neutral-500 font-light">{formatRelativeTime(study.updated_at)}</span>
        </div>
      </Card>
    </Link>
  );
}
