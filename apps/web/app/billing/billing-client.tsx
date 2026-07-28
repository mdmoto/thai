"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Check, Loader2 } from "lucide-react";
import {
  BillingPackage,
  createOrderApi,
  getCatalogApi,
  getEntitlementTransactionsApi,
  getMeApi,
  getOrdersApi,
  getTransactionsApi,
  PurchaseOrder,
  UserProfile,
} from "@/lib/api-client";
import { Card } from "@/components/ui";

type Transaction = {
  id: string;
  amount: number;
  type: string;
  description?: string;
  balance_after?: number;
  created_at: string;
};

const SALES_URL =
  process.env.NEXT_PUBLIC_SALES_URL || "https://wa.me/66623458238";

const PACKAGE_LABELS: Record<string, string> = {
  BASIC_DECISION_SINGLE: "单次基础决策",
  STARTER: "单次专业决策包",
  GROWTH: "增长团队包",
  SCALE: "规模化决策包",
  PREVIEW: "免费预览",
  STANDARD: "基础模拟",
  BASIC_DECISION: "基础决策",
  PROFESSIONAL: "深度决策",
  DEEP: "专属研究",
  ENTERPRISE: "企业定制",
};

const PACKAGE_POPULATION: Record<string, string> = {
  BASIC_DECISION_SINGLE: "每次覆盖 20,000 人 AI 模拟消费人群",
  STARTER: "每次覆盖 300,000 人 AI 模拟消费人群",
  GROWTH: "每次覆盖 300,000 人 AI 模拟消费人群",
  SCALE: "每次覆盖 300,000 人 AI 模拟消费人群",
};

const ORDER_STATUS_LABELS: Record<string, string> = {
  PENDING: "待付款",
  PAYMENT_PENDING: "等待付款核验",
  PAID: "已付款",
  VERIFIED: "已核验并入账",
  CANCELLED: "已取消",
  EXPIRED: "已过期",
  FAILED: "处理失败",
};

const TRANSACTION_TYPE_LABELS: Record<string, string> = {
  PURCHASE: "购买次数",
  PURCHASE_BONUS: "套餐赠送积分",
  RESERVATION: "运行预留积分",
  RUN_RESERVATION: "运行消耗",
  CONSUMPTION: "运行消耗积分",
  REFUND: "退回积分",
  FAILED_RUN_REFUND: "失败自动退回",
  INVITE_BONUS: "邀请码赠送积分",
  ADJUSTMENT: "人工调整",
};

function entitlementSummary(entitlements: Record<string, number>): string {
  const parts: string[] = [];
  if (entitlements.BASIC_DECISION) {
    parts.push(`${entitlements.BASIC_DECISION} 次基础决策`);
  }
  if (entitlements.PROFESSIONAL) {
    parts.push(`${entitlements.PROFESSIONAL} 次深度决策`);
  }
  return parts.join(" · ");
}

function salesUrlForOrder(order: PurchaseOrder): string {
  const separator = SALES_URL.includes("?") ? "&" : "?";
  const message = [
    "Chiang Mai AI Center 付款咨询",
    `订单编号：${order.id}`,
    `套餐：${PACKAGE_LABELS[order.package_code] ?? order.package_code}`,
    `金额：THB ${(order.amount_minor / 100).toLocaleString()}`,
  ].join("\n");
  return `${SALES_URL}${separator}text=${encodeURIComponent(message)}`;
}

export function BillingClient() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [packages, setPackages] = useState<BillingPackage[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [entitlementTransactions, setEntitlementTransactions] = useState<
    Array<Transaction & { plan_code: string }>
  >([]);
  const [creating, setCreating] = useState<string | null>(null);
  const [createdOrder, setCreatedOrder] = useState<PurchaseOrder | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    Promise.all([
      getMeApi(),
      getCatalogApi(),
      getOrdersApi(),
      getTransactionsApi(),
      getEntitlementTransactionsApi(),
    ])
      .then(([profile, catalog, orderList, transactionList, entitlementList]) => {
        setUser(profile);
        setPackages(catalog.packages);
        setOrders(orderList);
        setTransactions(transactionList);
        setEntitlementTransactions(entitlementList);
      })
      .catch(err => setError(err instanceof Error ? err.message : "读取账单失败"));

  useEffect(() => {
    load();
  }, []);

  const createOrder = async (packageCode: string) => {
    setCreating(packageCode);
    setError(null);
    try {
      const order = await createOrderApi(packageCode);
      setCreatedOrder(order);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建订单失败");
    } finally {
      setCreating(null);
    }
  };

  if (error && !user) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <Card>
          <p className="text-sm text-rose-300">{error}</p>
          <Link href="/login" className="btn-cmai-primary mt-4">登录后购买</Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-5 sm:p-8 max-w-6xl mx-auto space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <span className="eyebrow">决策次数、赠送积分与已核验订单</span>
          <h1 className="text-2xl font-semibold text-white mt-2">购买决策服务</h1>
          <p className="text-sm text-neutral-400 mt-2 max-w-2xl">
            选择一种套餐创建订单。付款由销售团队核验，到账后决策次数和赠送积分自动入账。
          </p>
        </div>
        <Card className="!p-4 min-w-64">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <div className="text-2xl font-semibold text-white tabular-nums">
                {user?.credits_balance ?? "—"}
              </div>
              <div className="text-[11px] text-neutral-500 mt-1">赠送积分</div>
            </div>
            <div>
              <div className="text-2xl font-semibold text-white tabular-nums">
                {user?.basic_decision_runs_balance ?? "—"}
              </div>
              <div className="text-[11px] text-neutral-500 mt-1">基础决策</div>
            </div>
            <div>
              <div className="text-2xl font-semibold text-white tabular-nums">
                {user?.deep_decision_runs_balance ?? "—"}
              </div>
              <div className="text-[11px] text-neutral-500 mt-1">深度决策</div>
            </div>
          </div>
        </Card>
      </div>

      {error && <p className="text-sm text-rose-300">{error}</p>}

      {createdOrder && (
        <Card className="border-neutral-700">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-white text-black flex items-center justify-center">
              <Check size={15} />
            </div>
            <div className="flex-1">
              <h2 className="text-sm font-semibold text-white">订单已创建</h2>
              <p className="text-xs text-neutral-400 mt-1">
                订单编号 <span className="font-mono text-white">{createdOrder.id}</span>。
                联系销售时请附上该编号，到账核验后系统自动记入决策次数和赠送积分。
              </p>
              <a
                href={salesUrlForOrder(createdOrder)}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-cmai-primary mt-4"
              >
                通过 WhatsApp 联系官方销售 <ArrowUpRight size={14} />
              </a>
            </div>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {packages.map(pkg => (
          <Card key={pkg.code} className="flex flex-col">
            <h2 className="text-base font-semibold text-white">
              {PACKAGE_LABELS[pkg.code] ?? pkg.name}
            </h2>
            <div className="text-3xl font-semibold text-white mt-4">
              ฿{(pkg.amount_minor / 100).toLocaleString()}
            </div>
            <div className="text-xs text-neutral-500 mt-2">
              {PACKAGE_POPULATION[pkg.code]}
            </div>
            <div className="mt-5 space-y-2 flex-1">
              <div className="rounded-lg border border-neutral-900 bg-neutral-950 px-3 py-2 text-xs text-neutral-300">
                包含 {entitlementSummary(pkg.run_entitlements)}
              </div>
              {pkg.bonus_credits > 0 && (
                <div className="rounded-lg border border-emerald-950/70 bg-emerald-950/10 px-3 py-2 text-xs text-emerald-300">
                  {pkg.bonus_credits >= 5
                    ? `赠送 ${pkg.bonus_credits} 积分，可运行 ${Math.floor(
                        pkg.bonus_credits / 5,
                      )} 次基础模拟`
                    : `赠送 ${pkg.bonus_credits} 积分，可累计用于基础模拟`}
                </div>
              )}
            </div>
            <button
              onClick={() => createOrder(pkg.code)}
              disabled={creating !== null}
              className="btn-cmai-primary mt-5 w-full"
            >
              {creating === pkg.code ? <Loader2 size={14} className="animate-spin" /> : null}
              创建付款订单
            </button>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <span className="eyebrow">订单记录</span>
          <h2 className="text-sm font-semibold text-white mt-1 mb-4">最近订单</h2>
          <div className="space-y-3">
            {orders.length ? orders.slice(0, 8).map(order => (
              <div key={order.id} className="flex justify-between gap-4 text-xs border-b border-neutral-900 pb-3">
                <div>
                  <div className="text-white font-mono">{order.id}</div>
                  <div className="text-neutral-500 mt-1">
                    {PACKAGE_LABELS[order.package_code] ?? order.package_code}
                    {entitlementSummary(order.run_entitlements) ? ` · ${entitlementSummary(order.run_entitlements)}` : ""}
                    {order.bonus_credits > 0 ? ` · 赠 ${order.bonus_credits} 积分` : ""}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-neutral-300">฿{(order.amount_minor / 100).toLocaleString()}</div>
                  <div className="text-neutral-500 mt-1">{ORDER_STATUS_LABELS[order.status] ?? order.status}</div>
                </div>
              </div>
            )) : <p className="text-xs text-neutral-500">暂无订单。</p>}
          </div>
        </Card>

        <Card>
          <span className="eyebrow">积分流水</span>
          <h2 className="text-sm font-semibold text-white mt-1 mb-4">积分流水</h2>
          <div className="space-y-3">
            {transactions.length ? transactions.slice(0, 8).map(item => (
              <div key={item.id} className="flex justify-between gap-4 text-xs border-b border-neutral-900 pb-3">
                <div>
                  <div className="text-neutral-300">{item.description || TRANSACTION_TYPE_LABELS[item.type] || item.type}</div>
                  <div className="text-neutral-500 mt-1">
                    {new Date(item.created_at).toLocaleString()}
                  </div>
                </div>
                <div className={item.amount >= 0 ? "text-emerald-400" : "text-neutral-300"}>
                  {item.amount >= 0 ? "+" : ""}{item.amount}
                </div>
              </div>
            )) : <p className="text-xs text-neutral-500">暂无流水。</p>}
          </div>
        </Card>

        <Card>
          <span className="eyebrow">决策次数流水</span>
          <h2 className="text-sm font-semibold text-white mt-1 mb-4">次数变动</h2>
          <div className="space-y-3">
            {entitlementTransactions.length ? entitlementTransactions.slice(0, 8).map(item => (
              <div key={item.id} className="flex justify-between gap-4 text-xs border-b border-neutral-900 pb-3">
                <div>
                  <div className="text-neutral-300">{item.description || TRANSACTION_TYPE_LABELS[item.type] || item.type}</div>
                  <div className="text-neutral-500 mt-1">
                    {PACKAGE_LABELS[item.plan_code] ?? item.plan_code} · {new Date(item.created_at).toLocaleString()}
                  </div>
                </div>
                <div className={item.amount >= 0 ? "text-emerald-400" : "text-neutral-300"}>
                  {item.amount >= 0 ? "+" : ""}{item.amount}
                </div>
              </div>
            )) : <p className="text-xs text-neutral-500">暂无次数流水。</p>}
          </div>
        </Card>
      </div>
    </div>
  );
}
