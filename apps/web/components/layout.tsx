"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { clsx } from "clsx";
import {
  LayoutDashboard, FlaskConical, FileText, CreditCard,
  Users, Settings, ChevronLeft, ChevronRight, Bell,
  Globe, LogOut, Shield, Zap,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/dashboard",  label: "控制台",  icon: LayoutDashboard },
  { href: "/studies",    label: "研究项目", icon: FlaskConical },
  { href: "/templates",  label: "模板库",   icon: FileText },
  { href: "/billing",    label: "账单",     icon: CreditCard },
  { href: "/team",       label: "团队",     icon: Users },
  { href: "/account",    label: "账户",     icon: Settings },
];

const LOCALES = [
  { code: "zh", label: "中文" },
  { code: "en", label: "EN" },
  { code: "th", label: "ไทย" },
];

function setLocaleCookie(locale: string) {
  document.cookie = `locale=${locale};path=/;max-age=31536000`;
  window.location.reload();
}

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [locale, setLocale] = useState("zh");
  const [showLang, setShowLang] = useState(false);

  return (
    <aside
      className={clsx(
        "flex flex-col h-screen sticky top-0 transition-all duration-300 shrink-0",
        "border-r border-[var(--color-border-subtle)]",
        "bg-[var(--color-bg-surface)]",
        collapsed ? "w-16" : "w-60"
      )}
    >
      {/* Logo */}
      <div className={clsx(
        "flex items-center gap-3 px-4 py-5 border-b border-[var(--color-border-subtle)]",
        collapsed && "justify-center"
      )}>
        <div className="flex items-center justify-center w-8 h-8 rounded-lg shrink-0"
          style={{ background: "linear-gradient(135deg, #D4A853, #B8902E)" }}>
          <Zap size={16} className="text-[#0A1628]" />
        </div>
        {!collapsed && (
          <div>
            <div className="text-sm font-bold text-gradient-gold leading-none">Market Twin</div>
            <div className="text-[10px] text-muted mt-0.5">泰国市场孪生</div>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 space-y-0.5 px-2 overflow-y-auto">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-smooth group",
                active
                  ? "bg-[var(--color-gold-glow)] text-[var(--color-gold)] font-medium"
                  : "text-secondary hover:bg-[var(--color-bg-elevated)] hover:text-primary"
              )}
              title={collapsed ? label : undefined}
            >
              <Icon size={18} className={clsx("shrink-0", active && "text-[var(--color-gold)]")} />
              {!collapsed && <span>{label}</span>}
              {active && !collapsed && (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-[var(--color-gold)]" />
              )}
            </Link>
          );
        })}

        {/* Admin */}
        <Link
          href="/admin"
          className={clsx(
            "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-smooth mt-2",
            pathname.startsWith("/admin")
              ? "bg-[var(--color-gold-glow)] text-[var(--color-gold)] font-medium"
              : "text-muted hover:bg-[var(--color-bg-elevated)] hover:text-secondary"
          )}
          title={collapsed ? "管理后台" : undefined}
        >
          <Shield size={18} className="shrink-0" />
          {!collapsed && <span>管理后台</span>}
        </Link>
      </nav>

      {/* Bottom area */}
      <div className="p-2 border-t border-[var(--color-border-subtle)] space-y-1">
        {/* Language switcher */}
        <div className="relative">
          <button
            onClick={() => setShowLang(!showLang)}
            className={clsx(
              "btn-ghost w-full text-muted hover:text-secondary",
              collapsed && "justify-center px-0"
            )}
          >
            <Globe size={16} />
            {!collapsed && <span className="text-xs">{LOCALES.find(l => l.code === locale)?.label}</span>}
          </button>
          {showLang && (
            <div className="absolute bottom-full left-0 mb-1 glass-card p-1 min-w-24 z-50 animate-fade-in">
              {LOCALES.map(l => (
                <button
                  key={l.code}
                  className={clsx(
                    "w-full text-left px-3 py-1.5 text-sm rounded-md transition-smooth",
                    locale === l.code ? "text-gold bg-[var(--color-gold-glow)]" : "text-secondary hover:bg-elevated hover:text-primary"
                  )}
                  onClick={() => {
                    setLocale(l.code);
                    setShowLang(false);
                    setLocaleCookie(l.code);
                  }}
                >
                  {l.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* User */}
        <div className={clsx(
          "flex items-center gap-2 px-2 py-1.5 rounded-lg",
          collapsed ? "justify-center" : ""
        )}>
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#D4A853] to-[#B8902E] flex items-center justify-center shrink-0">
            <span className="text-[10px] font-bold text-[#0A1628]">A</span>
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-primary truncate">Adam</div>
              <div className="text-[10px] text-muted truncate">Professional</div>
            </div>
          )}
          {!collapsed && (
            <button className="text-muted hover:text-red-400 transition-smooth">
              <LogOut size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -right-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-[var(--color-bg-elevated)] border border-[var(--color-border)] flex items-center justify-center text-muted hover:text-primary transition-smooth z-10"
      >
        {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
      </button>
    </aside>
  );
}

// ─────────────────────────────────────────
// Top Bar
// ─────────────────────────────────────────
export function TopBar({ title, actions }: { title?: string; actions?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)]/60 backdrop-blur-sm sticky top-0 z-30">
      {title && (
        <h1 className="text-base font-semibold text-primary">{title}</h1>
      )}
      <div className="flex items-center gap-3 ml-auto">
        {actions}
        <button className="relative text-muted hover:text-primary transition-smooth">
          <Bell size={18} />
          <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-[var(--color-gold)] animate-pulse" />
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────
// App Shell
// ─────────────────────────────────────────
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-base">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
