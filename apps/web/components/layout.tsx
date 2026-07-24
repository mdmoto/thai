"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { clsx } from "clsx";
import {
  LayoutDashboard, FlaskConical, FileText, CreditCard,
  Users, Settings, ChevronLeft, ChevronRight, Bell,
  Globe, LogOut, Shield, ArrowUpRight,
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
  { code: "en", label: "English" },
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
        "border-r border-neutral-900 bg-base",
        collapsed ? "w-16" : "w-56"
      )}
    >
      {/* Brand Header */}
      <div className={clsx(
        "flex items-center gap-3 px-5 h-16 border-b border-neutral-900",
        collapsed && "justify-center px-0"
      )}>
        <Link href="/dashboard" className="flex items-center gap-2.5 group">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center font-display font-bold text-xs tracking-tighter shrink-0 transition-transform group-hover:scale-105"
            style={{ background: "linear-gradient(135deg, #E8C879, #B8902E)", color: "#1d1508" }}
          >
            MT
          </div>
          {!collapsed && (
            <div>
              <div className="text-[13px] font-semibold text-white leading-tight tracking-tight">Market Twin</div>
              <div className="text-[10px] text-neutral-400 font-light">Thailand Platform</div>
            </div>
          )}
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 space-y-0.5 px-3 overflow-y-auto">
        {!collapsed && (
          <div className="px-2 mb-2 text-[10px] uppercase font-mono tracking-widest text-neutral-400 font-semibold">
            Platform
          </div>
        )}
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium transition-colors group",
                active
                  ? "bg-neutral-900 text-white"
                  : "text-neutral-400 hover:text-white hover:bg-neutral-900/60"
              )}
              title={collapsed ? label : undefined}
            >
              <Icon size={16} className={clsx("shrink-0", active ? "text-white" : "text-neutral-400 group-hover:text-white")} />
              {!collapsed && <span>{label}</span>}
              {active && !collapsed && (
                <span className="ml-auto w-1 h-1 rounded-full bg-[#D4A853]" />
              )}
            </Link>
          );
        })}

        {!collapsed && (
          <div className="px-2 pt-4 mb-2 text-[10px] uppercase font-mono tracking-widest text-neutral-400 font-semibold">
            Admin & Site
          </div>
        )}
        <Link
          href="/admin"
          className={clsx(
            "flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium transition-colors text-neutral-400 hover:text-white hover:bg-neutral-900/60",
            pathname.startsWith("/admin") && "bg-neutral-900 text-white"
          )}
          title={collapsed ? "管理后台" : undefined}
        >
          <Shield size={16} className="shrink-0" />
          {!collapsed && <span>管理后台</span>}
        </Link>

        <a
          href="https://lazzor.com"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium text-neutral-400 hover:text-white hover:bg-neutral-900/60 transition-colors"
          title={collapsed ? "Lazzor 官网" : undefined}
        >
          <ArrowUpRight size={16} className="shrink-0" />
          {!collapsed && <span>Lazzor.com</span>}
        </a>
      </nav>

      {/* Footer Area */}
      <div className="p-3 border-t border-neutral-900 space-y-1">
        {/* Language selector */}
        <div className="relative">
          <button
            onClick={() => setShowLang(!showLang)}
            className={clsx(
              "btn-lazzor-ghost w-full justify-start text-[12px] text-neutral-400 hover:text-white px-2 py-1.5",
              collapsed && "justify-center px-0"
            )}
          >
            <Globe size={14} />
            {!collapsed && <span>{LOCALES.find(l => l.code === locale)?.label}</span>}
          </button>
          {showLang && (
            <div className="absolute bottom-full left-0 mb-2 bg-neutral-900 border border-neutral-800 rounded-xl p-1.5 min-w-28 z-50 shadow-2xl">
              {LOCALES.map(l => (
                <button
                  key={l.code}
                  className={clsx(
                    "w-full text-left px-3 py-1.5 text-xs rounded-lg transition-colors",
                    locale === l.code ? "text-white bg-neutral-800 font-medium" : "text-neutral-400 hover:text-white hover:bg-neutral-800/50"
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

        {/* User Card */}
        <div className={clsx(
          "flex items-center gap-2.5 px-2 py-1.5 rounded-lg bg-neutral-900/40 border border-neutral-900",
          collapsed && "justify-center"
        )}>
          <div className="w-6 h-6 rounded-full bg-white text-black text-[10px] font-bold flex items-center justify-center shrink-0">
            A
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-white truncate">Adam</div>
              <div className="text-[10px] text-neutral-400 truncate">Professional</div>
            </div>
          )}
          {!collapsed && (
            <button className="text-neutral-500 hover:text-rose-400 transition-colors">
              <LogOut size={13} />
            </button>
          )}
        </div>
      </div>

      {/* Collapse Toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -right-3 top-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-neutral-900 border border-neutral-800 flex items-center justify-center text-neutral-400 hover:text-white transition-colors z-10"
      >
        {collapsed ? <ChevronRight size={11} /> : <ChevronLeft size={11} />}
      </button>
    </aside>
  );
}

// ─────────────────────────────────────────
// TopBar
// ─────────────────────────────────────────
export function TopBar({ title, actions }: { title?: string; actions?: React.ReactNode }) {
  return (
    <header className="flex items-center justify-between px-8 h-16 border-b border-neutral-900 bg-black/80 backdrop-blur-md sticky top-0 z-30">
      {title && (
        <h1 className="text-sm font-semibold text-neutral-100 tracking-tight">{title}</h1>
      )}
      <div className="flex items-center gap-3 ml-auto">
        {actions}
        <button className="relative p-2 rounded-full border border-neutral-800 text-neutral-400 hover:text-white hover:border-neutral-700 transition-colors">
          <Bell size={15} />
          <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-emerald-500" />
        </button>
      </div>
    </header>
  );
}

// ─────────────────────────────────────────
// AppShell
// ─────────────────────────────────────────
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-base text-neutral-100">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-base">
        {children}
      </main>
    </div>
  );
}
