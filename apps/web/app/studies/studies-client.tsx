"use client";

import Link from "next/link";
import { useState } from "react";
import { Search, Filter, ArrowRight, LayoutGrid, List } from "lucide-react";
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
    <div className="p-6 space-y-5 animate-fade-in">
      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            type="text"
            placeholder="搜索项目名称..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="input-field pl-9 w-full"
          />
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-[var(--color-bg-elevated)] rounded-lg p-1">
            {STATUS_FILTERS.map(f => (
              <button
                key={f.value}
                onClick={() => setStatusFilter(f.value)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-smooth ${
                  statusFilter === f.value
                    ? "bg-[var(--color-gold-glow)] text-gold"
                    : "text-muted hover:text-secondary"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1 bg-[var(--color-bg-elevated)] rounded-lg p-1">
            <button
              onClick={() => setView("list")}
              className={`p-1.5 rounded-md transition-smooth ${view === "list" ? "bg-[var(--color-bg-hover)] text-primary" : "text-muted"}`}
            >
              <List size={16} />
            </button>
            <button
              onClick={() => setView("grid")}
              className={`p-1.5 rounded-md transition-smooth ${view === "grid" ? "bg-[var(--color-bg-hover)] text-primary" : "text-muted"}`}
            >
              <LayoutGrid size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Results count */}
      <p className="text-xs text-muted">
        共 <span className="text-secondary font-medium">{filtered.length}</span> 个项目
      </p>

      {/* Studies */}
      {filtered.length === 0 ? (
        <Card>
          <EmptyState
            icon="🔍"
            title="没有找到匹配的项目"
            description="尝试修改搜索词或筛选条件"
          />
        </Card>
      ) : view === "list" ? (
        <div className="space-y-2 stagger-children">
          {filtered.map(study => (
            <StudyListItem key={study.id} study={study} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 stagger-children">
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
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center text-xl shrink-0"
            style={{ background: `${meta?.color}18` }}
          >
            {meta?.icon}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <StatusBadge status={study.status as Parameters<typeof StatusBadge>[0]["status"]} />
              <PlanBadge plan={study.plan_code as Parameters<typeof PlanBadge>[0]["plan"]} />
              <span className="text-xs text-muted">{meta?.label}</span>
            </div>
            <p className="font-medium text-primary truncate">{study.name}</p>
          </div>
          <div className="hidden sm:flex flex-col items-end gap-1 shrink-0">
            <span className="text-xs text-muted">{formatRelativeTime(study.updated_at)}</span>
            <ArrowRight size={16} className="text-muted" />
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
      <Card hover className="h-full">
        <div className="flex items-start justify-between mb-3">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center text-xl"
            style={{ background: `${meta?.color}18` }}
          >
            {meta?.icon}
          </div>
          <StatusBadge status={study.status as Parameters<typeof StatusBadge>[0]["status"]} />
        </div>
        <h3 className="font-medium text-primary text-sm mb-2 line-clamp-2">{study.name}</h3>
        <div className="flex items-center justify-between mt-auto">
          <PlanBadge plan={study.plan_code as Parameters<typeof PlanBadge>[0]["plan"]} />
          <span className="text-xs text-muted">{formatRelativeTime(study.updated_at)}</span>
        </div>
      </Card>
    </Link>
  );
}
