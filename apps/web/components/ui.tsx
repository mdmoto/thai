"use client";

import { clsx } from "clsx";

// ─────────────────────────────────────────
// Status Badge
// ─────────────────────────────────────────
type StatusType =
  | "DRAFT" | "PARSING" | "NEEDS_CONFIRMATION" | "READY"
  | "QUEUED" | "PREPARING_POPULATION" | "RUNNING_AGENTS"
  | "RUNNING_SIMULATION" | "RUNNING_SCENARIOS" | "GENERATING_REPORT"
  | "COMPLETED" | "PAUSED" | "RETRYING" | "FAILED_RECOVERABLE"
  | "FAILED_FINAL" | "CANCEL_REQUESTED" | "CANCELLED" | "EXPIRED";

const STATUS_CONFIG: Record<StatusType, { label: string; color: string; dot: string }> = {
  DRAFT:                { label: "草稿",       color: "text-[#8FA3C0] bg-[#1C3259]/40", dot: "#4A6280" },
  PARSING:              { label: "解析中",     color: "text-blue-400 bg-blue-500/10",   dot: "#3B82F6" },
  NEEDS_CONFIRMATION:   { label: "待确认",     color: "text-amber-400 bg-amber-500/10", dot: "#F59E0B" },
  READY:                { label: "准备就绪",   color: "text-emerald-400 bg-emerald-500/10", dot: "#10B981" },
  QUEUED:               { label: "排队中",     color: "text-sky-400 bg-sky-500/10",     dot: "#38BDF8" },
  PREPARING_POPULATION: { label: "构建人口",   color: "text-violet-400 bg-violet-500/10", dot: "#8B5CF6" },
  RUNNING_AGENTS:       { label: "消费者推理", color: "text-violet-400 bg-violet-500/10", dot: "#8B5CF6" },
  RUNNING_SIMULATION:   { label: "群体模拟",   color: "text-violet-400 bg-violet-500/10", dot: "#8B5CF6" },
  RUNNING_SCENARIOS:    { label: "情景对比",   color: "text-violet-400 bg-violet-500/10", dot: "#8B5CF6" },
  GENERATING_REPORT:    { label: "生成报告",   color: "text-violet-400 bg-violet-500/10", dot: "#8B5CF6" },
  COMPLETED:            { label: "已完成",     color: "text-emerald-400 bg-emerald-500/10", dot: "#10B981" },
  PAUSED:               { label: "已暂停",     color: "text-amber-400 bg-amber-500/10", dot: "#F59E0B" },
  RETRYING:             { label: "重试中",     color: "text-orange-400 bg-orange-500/10", dot: "#F97316" },
  FAILED_RECOVERABLE:   { label: "可恢复失败", color: "text-orange-400 bg-orange-500/10", dot: "#F97316" },
  FAILED_FINAL:         { label: "已失败",     color: "text-red-400 bg-red-500/10",     dot: "#EF4444" },
  CANCEL_REQUESTED:     { label: "取消中",     color: "text-[#8FA3C0] bg-[#1C3259]/40", dot: "#4A6280" },
  CANCELLED:            { label: "已取消",     color: "text-[#8FA3C0] bg-[#1C3259]/40", dot: "#4A6280" },
  EXPIRED:              { label: "已过期",     color: "text-[#8FA3C0] bg-[#1C3259]/40", dot: "#4A6280" },
};

export function StatusBadge({ status }: { status: StatusType }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.DRAFT;
  const isRunning = ["PARSING","PREPARING_POPULATION","RUNNING_AGENTS","RUNNING_SIMULATION","RUNNING_SCENARIOS","GENERATING_REPORT","RETRYING"].includes(status);
  return (
    <span className={clsx("status-badge", cfg.color)}>
      <span
        className={clsx("glow-dot", isRunning && "animate-pulse")}
        style={{ backgroundColor: cfg.dot, color: cfg.dot }}
      />
      {cfg.label}
    </span>
  );
}

// ─────────────────────────────────────────
// Plan Badge
// ─────────────────────────────────────────
type PlanCode = "PREVIEW" | "STANDARD" | "PROFESSIONAL" | "DEEP" | "ENTERPRISE";

const PLAN_CONFIG: Record<PlanCode, { label: string; color: string }> = {
  PREVIEW:      { label: "预览版",   color: "text-gray-400 bg-gray-500/10" },
  STANDARD:     { label: "标准版",   color: "text-sky-400 bg-sky-500/10" },
  PROFESSIONAL: { label: "专业版",   color: "text-[#D4A853] bg-[#D4A853]/10" },
  DEEP:         { label: "深度版",   color: "text-violet-400 bg-violet-500/10" },
  ENTERPRISE:   { label: "企业版",   color: "text-emerald-400 bg-emerald-500/10" },
};

export function PlanBadge({ plan }: { plan: PlanCode }) {
  const cfg = PLAN_CONFIG[plan];
  return <span className={clsx("status-badge font-semibold", cfg.color)}>{cfg.label}</span>;
}

// ─────────────────────────────────────────
// Skeleton Loader
// ─────────────────────────────────────────
export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={clsx("shimmer rounded-lg", className)} />
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
    <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-in">
      {icon && (
        <div className="text-4xl mb-4 opacity-40">{icon}</div>
      )}
      <h3 className="text-base font-medium text-secondary mb-2">{title}</h3>
      {description && (
        <p className="text-sm text-muted max-w-sm mb-6">{description}</p>
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
}: {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  hover?: boolean;
}) {
  return (
    <div
      className={clsx(
        "glass-card p-5 transition-smooth",
        hover && "cursor-pointer hover:border-[var(--color-gold-dim)] hover:bg-[var(--color-bg-hover)]",
        className
      )}
      onClick={onClick}
    >
      {children}
    </div>
  );
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
        <label className="block text-sm font-medium text-secondary">
          {label}
          {props.required && <span className="text-[var(--color-gold)] ml-1">*</span>}
        </label>
      )}
      <input
        className={clsx(
          "input-field",
          error && "border-red-500 focus:border-red-500 focus:shadow-[0_0_0_3px_rgba(239,68,68,0.1)]",
          className
        )}
        {...props}
      />
      {error && <p className="text-xs text-red-400">{error}</p>}
      {hint && !error && <p className="text-xs text-muted">{hint}</p>}
    </div>
  );
}

// ─────────────────────────────────────────
// Spinner
// ─────────────────────────────────────────
export function Spinner({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className="animate-spin"
    >
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="3"
        strokeOpacity="0.2"
      />
      <path
        d="M12 2a10 10 0 0 1 10 10"
        stroke="var(--color-gold)"
        strokeWidth="3"
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
    <div className={clsx("space-y-1", className)}>
      {(label || sublabel) && (
        <div className="flex justify-between items-center">
          <span className="text-sm font-medium text-primary">{label}</span>
          <span className="text-xs text-muted">{sublabel}</span>
        </div>
      )}
      <div className="h-1.5 bg-[var(--color-bg-elevated)] rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${pct}%`,
            background: pct === 100
              ? "var(--color-success)"
              : "linear-gradient(90deg, var(--color-gold-dim), var(--color-gold))",
          }}
        />
      </div>
    </div>
  );
}
