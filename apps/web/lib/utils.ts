import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function parseApiDate(iso: string) {
  const value = iso.trim();
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  return new Date(hasTimezone ? value : `${value}Z`);
}

export function formatDate(iso: string, locale = "zh-CN") {
  return new Intl.DateTimeFormat(locale, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parseApiDate(iso));
}

export function formatRelativeTime(iso: string) {
  const now = Date.now();
  const then = parseApiDate(iso).getTime();
  if (!Number.isFinite(then)) return "时间未知";

  const diff = Math.max(0, now - then);
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  if (hours < 24) return `${hours} 小时前`;
  return `${days} 天前`;
}

export function formatNumber(n: number, decimals = 0) {
  return new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

export function formatPercent(n: number, decimals = 1) {
  return `${(n * 100).toFixed(decimals)}%`;
}

export function formatTHB(n: number) {
  return new Intl.NumberFormat("th-TH", {
    style: "currency",
    currency: "THB",
    minimumFractionDigits: 0,
  }).format(n);
}

export function isRunning(status: string) {
  return [
    "PARSING", "QUEUED", "PREPARING_POPULATION",
    "RUNNING_AGENTS", "RUNNING_SIMULATION",
    "RUNNING_SCENARIOS", "GENERATING_REPORT", "RETRYING"
  ].includes(status);
}

export function isTerminal(status: string) {
  return ["COMPLETED", "FAILED_FINAL", "CANCELLED", "EXPIRED"].includes(status);
}

export function needsAction(status: string) {
  return ["NEEDS_CONFIRMATION", "FAILED_RECOVERABLE", "PAUSED"].includes(status);
}
