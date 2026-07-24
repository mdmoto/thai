"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { clsx } from "clsx";
import {
  ChevronLeft,
  ChevronRight,
  CreditCard,
  FileText,
  FlaskConical,
  LayoutDashboard,
  LogOut,
  PlusCircle,
  User as UserIcon,
  Zap,
} from "lucide-react";
import { AuthModal } from "@/components/auth-modal";
import {
  AUTH_EVENT,
  StoredUser,
  clearAuthSession,
  getStoredUser,
  updateStoredUser,
} from "@/lib/auth-session";
import { getMeApi } from "@/lib/api-client";

const NAV_ITEMS = [
  { href: "/dashboard", label: "控制台", icon: LayoutDashboard },
  { href: "/studies", label: "研究项目", icon: FlaskConical },
  { href: "/templates", label: "模板库", icon: FileText },
  { href: "/billing", label: "额度与订单", icon: CreditCard },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [user, setUser] = useState<StoredUser | null>(null);
  const [showAuthModal, setShowAuthModal] = useState(false);

  useEffect(() => {
    const cached = getStoredUser();
    setUser(cached);
    if (cached) {
      getMeApi()
        .then(profile => {
          setUser(profile);
          updateStoredUser(profile);
        })
        .catch(() => setUser(null));
    }
    const syncAuth = (event: Event) => {
      setUser((event as CustomEvent<StoredUser | null>).detail);
    };
    window.addEventListener(AUTH_EVENT, syncAuth);
    return () => window.removeEventListener(AUTH_EVENT, syncAuth);
  }, []);

  const handleLogout = () => {
    clearAuthSession();
    setUser(null);
  };

  return (
    <>
      <aside
        className={clsx(
          "flex flex-col h-screen sticky top-0 transition-all duration-300 shrink-0",
          "border-r border-neutral-900 bg-base",
          collapsed ? "w-16" : "w-56",
        )}
      >
        <div
          className={clsx(
            "flex items-center gap-3 px-5 h-16 border-b border-neutral-900",
            collapsed && "justify-center px-0",
          )}
        >
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-7 h-7 rounded-lg bg-neutral-900 border border-neutral-800 flex items-center justify-center font-bold text-xs tracking-tighter shrink-0 text-white">
              MT
            </div>
            {!collapsed && (
              <div>
                <div className="text-[13px] font-semibold text-white leading-tight tracking-tight">
                  Market Twin
                </div>
                <div className="text-[10px] text-neutral-400 font-light">
                  Thailand Consumer Lab
                </div>
              </div>
            )}
          </Link>
        </div>

        <nav className="flex-1 py-4 space-y-0.5 px-3 overflow-y-auto">
          {!collapsed && (
            <div className="px-2 mb-2 text-[10px] uppercase font-mono tracking-widest text-neutral-400 font-semibold">
              Workspace
            </div>
          )}
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                className={clsx(
                  "flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium transition-colors group",
                  active
                    ? "bg-neutral-900 text-white"
                    : "text-neutral-400 hover:text-white hover:bg-neutral-900/60",
                )}
                title={collapsed ? label : undefined}
              >
                <Icon size={16} className="shrink-0" />
                {!collapsed && <span>{label}</span>}
                {active && !collapsed && (
                  <span className="ml-auto w-1 h-1 rounded-full bg-white" />
                )}
              </Link>
            );
          })}
        </nav>

        <div className="p-3 border-t border-neutral-900 space-y-2">
          {user ? (
            <div
              className={clsx(
                "p-2 rounded-xl bg-neutral-950 border border-neutral-900 space-y-2",
                collapsed && "text-center",
              )}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-6 h-6 rounded-full bg-neutral-700 text-white text-[10px] font-bold flex items-center justify-center shrink-0">
                    {user.name?.[0]?.toUpperCase() || "U"}
                  </div>
                  {!collapsed && (
                    <div className="min-w-0">
                      <div className="text-xs font-semibold text-white truncate">
                        {user.name || "用户"}
                      </div>
                      <div className="text-[10px] text-neutral-400 font-mono flex items-center gap-1">
                        <Zap size={10} /> {user.credits_balance} 积分
                      </div>
                    </div>
                  )}
                </div>
                {!collapsed && (
                  <button
                    onClick={handleLogout}
                    aria-label="退出登录"
                    className="text-neutral-500 hover:text-rose-400 transition-colors"
                  >
                    <LogOut size={13} />
                  </button>
                )}
              </div>
              {!collapsed && (
                <Link
                  href="/billing"
                  className="w-full btn-cmai-secondary text-[10px] py-1 px-2 rounded-lg justify-center font-mono"
                >
                  <PlusCircle size={12} /> 购买额度
                </Link>
              )}
            </div>
          ) : (
            <button
              onClick={() => setShowAuthModal(true)}
              className={clsx(
                "w-full btn-cmai-primary text-xs py-2 justify-center",
                collapsed && "px-0 text-[10px]",
              )}
            >
              <UserIcon size={14} /> {!collapsed && "登录 / 注册"}
            </button>
          )}
        </div>

        <button
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? "展开导航" : "收起导航"}
          className="absolute -right-3 top-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-neutral-900 border border-neutral-800 flex items-center justify-center text-neutral-400 hover:text-white transition-colors z-10"
        >
          {collapsed ? <ChevronRight size={11} /> : <ChevronLeft size={11} />}
        </button>
      </aside>

      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onSuccess={newUser => setUser(newUser)}
      />
    </>
  );
}

export function TopBar({
  title,
  actions,
}: {
  title?: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="flex items-center justify-between px-5 sm:px-8 h-16 border-b border-neutral-900 bg-black/80 backdrop-blur-md sticky top-0 z-30">
      {title && (
        <h1 className="text-sm font-semibold text-neutral-100 tracking-tight">
          {title}
        </h1>
      )}
      <div className="flex items-center gap-3 ml-auto">{actions}</div>
    </header>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-base text-neutral-100">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-base">{children}</main>
    </div>
  );
}
