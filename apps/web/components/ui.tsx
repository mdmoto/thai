"use client";

import { clsx } from "clsx";
import { useState, useEffect } from "react";

// ─────────────────────────────────────────
// Status Badge (CMAI / Lazzor pill style)
// ─────────────────────────────────────────
type StatusType =
  | "DRAFT" | "PARSING" | "NEEDS_CONFIRMATION" | "READY"
  | "QUEUED" | "PREPARING_POPULATION" | "RUNNING_AGENTS"
  | "RUNNING_SIMULATION" | "RUNNING_SCENARIOS" | "GENERATING_REPORT"
  | "COMPLETED" | "PAUSED" | "RETRYING" | "FAILED_RECOVERABLE"
  | "FAILED_FINAL" | "CANCEL_REQUESTED" | "CANCELLED" | "EXPIRED";

const STATUS_CONFIG: Record<StatusType, { label: string; dot: string; text: string }> = {
  DRAFT:                { label: "草稿",       dot: "bg-neutral-500", text: "text-neutral-400" },
  PARSING:              { label: "解析中",     dot: "bg-sky-400 animate-pulse", text: "text-sky-400" },
  NEEDS_CONFIRMATION:   { label: "待确认",     dot: "bg-amber-400 animate-pulse", text: "text-amber-400" },
  READY:                { label: "准备就绪",   dot: "bg-emerald-400", text: "text-emerald-400" },
  QUEUED:               { label: "排队中",     dot: "bg-sky-400", text: "text-sky-400" },
  PREPARING_POPULATION: { label: "构建人口",   dot: "bg-violet-400 animate-pulse", text: "text-violet-400" },
  RUNNING_AGENTS:       { label: "消费者推理", dot: "bg-violet-400 animate-pulse", text: "text-violet-400" },
  RUNNING_SIMULATION:   { label: "群体模拟",   dot: "bg-violet-400 animate-pulse", text: "text-violet-400" },
  RUNNING_SCENARIOS:    { label: "情景对比",   dot: "bg-violet-400 animate-pulse", text: "text-violet-400" },
  GENERATING_REPORT:    { label: "生成报告",   dot: "bg-violet-400 animate-pulse", text: "text-violet-400" },
  COMPLETED:            { label: "已完成",     dot: "bg-emerald-400", text: "text-emerald-400" },
  PAUSED:               { label: "已暂停",     dot: "bg-amber-400", text: "text-amber-400" },
  RETRYING:             { label: "重试中",     dot: "bg-amber-500 animate-pulse", text: "text-amber-400" },
  FAILED_RECOVERABLE:   { label: "可恢复失败", dot: "bg-amber-500", text: "text-amber-400" },
  FAILED_FINAL:         { label: "已失败",     dot: "bg-rose-500", text: "text-rose-400" },
  CANCEL_REQUESTED:     { label: "取消中",     dot: "bg-neutral-500", text: "text-neutral-400" },
  CANCELLED:            { label: "已取消",     dot: "bg-neutral-500", text: "text-neutral-400" },
  EXPIRED:              { label: "已过期",     dot: "bg-neutral-500", text: "text-neutral-400" },
};

export function StatusBadge({ status }: { status: StatusType }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.DRAFT;
  return (
    <span className={clsx("inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium border border-neutral-800 bg-[#070707]", cfg.text)}>
      <span className={clsx("w-1.5 h-1.5 rounded-full shrink-0", cfg.dot)} />
      {cfg.label}
    </span>
  );
}

// ─────────────────────────────────────────
// Plan Badge
// ─────────────────────────────────────────
type PlanCode = "PREVIEW" | "STANDARD" | "PROFESSIONAL" | "DEEP" | "ENTERPRISE";

const PLAN_LABELS: Record<PlanCode, string> = {
  PREVIEW: "Preview",
  STANDARD: "Standard",
  PROFESSIONAL: "Professional",
  DEEP: "Deep",
  ENTERPRISE: "Enterprise",
};

export function PlanBadge({ plan }: { plan: PlanCode }) {
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium font-mono border border-neutral-800 bg-[#070707] text-neutral-300">
      {PLAN_LABELS[plan]}
    </span>
  );
}

// ─────────────────────────────────────────
// Skeleton Loader
// ─────────────────────────────────────────
export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={clsx("animate-pulse bg-neutral-900 rounded-lg", className)} />
  );
}

// ─────────────────────────────────────────
// Empty State
// ─────────────────────────────────────────
export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {icon && <div className="text-3xl mb-3 text-neutral-500">{icon}</div>}
      <h3 className="text-sm font-medium text-neutral-200 mb-1">{title}</h3>
      {description && (
        <p className="text-xs text-[#86868b] max-w-sm mb-6 font-light">{description}</p>
      )}
      {action}
    </div>
  );
}

// ─────────────────────────────────────────
// Card
// ─────────────────────────────────────────
export function Card({
  children,
  className,
  onClick,
  hover = false,
  accent,
}: {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  hover?: boolean;
  /** Semantic accent — use only where the color carries real meaning. */
  accent?: "jade" | "gold" | "clay";
}) {
  return (
    <div
      className={clsx(
        "cmai-card p-6",
        accent && `card-accent-${accent}`,
        hover && "cursor-pointer hover:bg-[#151820]",
        className
      )}
      onClick={onClick}
    >
      {children}
    </div>
  );
}

// ─────────────────────────────────────────
// CountUp — animates a number from 0 to value
// ─────────────────────────────────────────
export function CountUp({ value, duration = 700 }: { value: number; duration?: number }) {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    let raf = 0;
    const start = performance.now();
    const from = 0;
    function tick(now: number) {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(Math.round(from + (value - from) * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);

  return <span className="tabular-nums">{display}</span>;
}

// ─────────────────────────────────────────
// Input
// ─────────────────────────────────────────
export function Input({
  label,
  error,
  hint,
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  error?: string;
  hint?: string;
}) {
  return (
    <div className="space-y-1.5">
      {label && (
        <label className="block text-xs font-medium text-[#86868b]">
          {label}
          {props.required && <span className="text-neutral-200 ml-1">*</span>}
        </label>
      )}
      <input
        className={clsx("input-cmai", error && "border-rose-500/50", className)}
        {...props}
      />
      {error && <p className="text-xs text-rose-400">{error}</p>}
      {hint && !error && <p className="text-xs text-[#515154] font-light">{hint}</p>}
    </div>
  );
}

// ─────────────────────────────────────────
// Spinner
// ─────────────────────────────────────────
export function Spinner({ size = 18 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className="animate-spin text-white"
    >
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="2"
        strokeOpacity="0.2"
      />
      <path
        d="M12 2a10 10 0 0 1 10 10"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

// ─────────────────────────────────────────
// Progress Bar
// ─────────────────────────────────────────
export function ProgressBar({
  value,
  max = 100,
  label,
  sublabel,
  className,
}: {
  value: number;
  max?: number;
  label?: string;
  sublabel?: string;
  className?: string;
}) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className={clsx("space-y-1.5", className)}>
      {(label || sublabel) && (
        <div className="flex justify-between items-center text-xs">
          <span className="font-medium text-neutral-300">{label}</span>
          <span className="text-[#86868b] font-light">{sublabel}</span>
        </div>
      )}
      <div className="h-1 bg-neutral-900 rounded-full overflow-hidden">
        <div
          className="h-full bg-white rounded-full transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
