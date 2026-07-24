"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { clsx } from "clsx";
import {
  LayoutDashboard, FlaskConical, FileText, CreditCard,
  Users, Settings, ChevronLeft, ChevronRight, Bell,
  Globe, LogOut, Shield, ArrowUpRight, Zap, User as UserIcon, PlusCircle,
} from "lucide-react";
import { AuthModal } from "@/components/auth-modal";
import { RechargeModal } from "@/components/recharge-modal";

const NAV_ITEMS = [
  { href: "/dashboard",  label: "控制台",  icon: LayoutDashboard },
  { href: "/studies",    label: "研究项目", icon: FlaskConical },
  { href: "/templates",  label: "模板库",   icon: FileText },
  { href: "/billing",    label: "账单/充值", icon: CreditCard },
  { href: "/team",       label: "团队",     icon: Users },
  { href: "/account",    label: "账户",     icon: Settings },
];

const LOCALES = [
  { code: "zh", label: "中文" },
  { code: "en", label: "English" },
  { code: "th", label: "ไทย" },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [locale, setLocale] = useState("zh");
  const [showLang, setShowLang] = useState(false);

  const [user, setUser] = useState<any>(null);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showRechargeModal, setShowRechargeModal] = useState(false);

  useEffect(() => {
    const cachedUser = localStorage.getItem("market_twin_user");
    if (cachedUser) {
      try { setUser(JSON.parse(cachedUser)); } catch (e) {}
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("market_twin_token");
    localStorage.removeItem("market_twin_user");
    setUser(null);
  };

  return (
    <>
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
            <div className="w-7 h-7 rounded-lg bg-neutral-900 border border-neutral-800 flex items-center justify-center font-bold text-xs tracking-tighter shrink-0 text-white">
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
                  <span className="ml-auto w-1 h-1 rounded-full bg-white" />
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

        {/* Footer Area with Credits & User Info */}
        <div className="p-3 border-t border-neutral-900 space-y-2">
          {user ? (
            <div className={clsx("p-2 rounded-xl bg-neutral-950 border border-neutral-900 space-y-2", collapsed && "text-center")}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-6 h-6 rounded-full bg-neutral-700 text-white text-[10px] font-bold flex items-center justify-center shrink-0">
                    {user.name ? user.name[0].toUpperCase() : "U"}
                  </div>
                  {!collapsed && (
                    <div className="min-w-0">
                      <div className="text-xs font-semibold text-white truncate">{user.name || "用户"}</div>
                      <div className="text-[10px] text-neutral-400 font-mono flex items-center gap-1">
                        <Zap size={10} /> {user.credits_balance ?? 50} 积分
                      </div>
                    </div>
                  )}
                </div>
                {!collapsed && (
                  <button onClick={handleLogout} className="text-neutral-500 hover:text-rose-400 transition-colors">
                    <LogOut size={13} />
                  </button>
                )}
              </div>
              {!collapsed && (
                <button
                  onClick={() => setShowRechargeModal(true)}
                  className="w-full btn-cmai-secondary text-[10px] py-1 px-2 rounded-lg justify-center font-mono"
                >
                  <PlusCircle size={12} /> 充值积分 / 升级套餐
                </button>
              )}
            </div>
          ) : (
            <button
              onClick={() => setShowAuthModal(true)}
              className={clsx(
                "w-full btn-cmai-primary text-xs py-2 justify-center",
                collapsed && "px-0 text-[10px]"
              )}
            >
              <UserIcon size={14} /> {!collapsed && "登录 / 注册 (送50积分)"}
            </button>
          )}
        </div>

        {/* Collapse Toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="absolute -right-3 top-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-neutral-900 border border-neutral-800 flex items-center justify-center text-neutral-400 hover:text-white transition-colors z-10"
        >
          {collapsed ? <ChevronRight size={11} /> : <ChevronLeft size={11} />}
        </button>
      </aside>

      {/* Auth & Recharge Modals */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onSuccess={(newUser) => setUser(newUser)}
      />
      <RechargeModal
        isOpen={showRechargeModal}
        onClose={() => setShowRechargeModal(false)}
        user={user}
        onRechargeSuccess={(newBalance) => {
          const updated = { ...user, credits_balance: newBalance };
          setUser(updated);
          localStorage.setItem("market_twin_user", JSON.stringify(updated));
        }}
      />
    </>
  );
}

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
          <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-neutral-400" />
        </button>
      </div>
    </header>
  );
}

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
