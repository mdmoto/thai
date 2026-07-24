"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Check, Loader2 } from "lucide-react";
import {
  BillingPackage,
  createOrderApi,
  getCatalogApi,
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

function salesUrlForOrder(order: PurchaseOrder): string {
  const separator = SALES_URL.includes("?") ? "&" : "?";
  const message = [
    "Thailand Market Twin 付款咨询",
    `订单编号：${order.id}`,
    `套餐：${order.package_code}`,
    `金额：THB ${(order.amount_minor / 100).toLocaleString()}`,
  ].join("\n");
  return `${SALES_URL}${separator}text=${encodeURIComponent(message)}`;
}

export function BillingClient() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [packages, setPackages] = useState<BillingPackage[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [creating, setCreating] = useState<string | null>(null);
  const [createdOrder, setCreatedOrder] = useState<PurchaseOrder | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    Promise.all([
      getMeApi(),
      getCatalogApi(),
      getOrdersApi(),
      getTransactionsApi(),
    ])
      .then(([profile, catalog, orderList, transactionList]) => {
        setUser(profile);
        setPackages(catalog.packages);
        setOrders(orderList);
        setTransactions(transactionList);
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
          <span className="eyebrow">Credits & verified orders</span>
          <h1 className="text-2xl font-semibold text-white mt-2">购买模拟额度</h1>
          <p className="text-sm text-neutral-400 mt-2 max-w-2xl">
            付款由销售团队核验，到账后积分才会入账。平台不会通过前端按钮自行增加余额。
          </p>
        </div>
        <Card className="!p-4 min-w-48">
          <div className="text-[11px] text-neutral-500">当前可用</div>
          <div className="text-3xl font-semibold text-white mt-1 tabular-nums">
            {user?.credits_balance ?? "—"}
          </div>
          <div className="text-[11px] text-neutral-500">积分</div>
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
                联系销售时请附上该编号，到账核验后系统自动记入积分。
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {packages.map(pkg => (
          <Card key={pkg.code} className="flex flex-col">
            <span className="eyebrow">{pkg.code}</span>
            <h2 className="text-base font-semibold text-white mt-2">{pkg.name}</h2>
            <div className="text-2xl font-semibold text-white mt-4">
              ฿{(pkg.amount_minor / 100).toLocaleString()}
            </div>
            <div className="text-xs text-neutral-400 mt-1">{pkg.credits} 积分</div>
            <p className="text-xs text-neutral-400 mt-4 leading-relaxed flex-1">
              {pkg.description}
            </p>
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <span className="eyebrow">Orders</span>
          <h2 className="text-sm font-semibold text-white mt-1 mb-4">最近订单</h2>
          <div className="space-y-3">
            {orders.length ? orders.slice(0, 8).map(order => (
              <div key={order.id} className="flex justify-between gap-4 text-xs border-b border-neutral-900 pb-3">
                <div>
                  <div className="text-white font-mono">{order.id}</div>
                  <div className="text-neutral-500 mt-1">{order.package_code} · {order.credits} 积分</div>
                </div>
                <div className="text-right">
                  <div className="text-neutral-300">฿{(order.amount_minor / 100).toLocaleString()}</div>
                  <div className="text-neutral-500 mt-1">{order.status}</div>
                </div>
              </div>
            )) : <p className="text-xs text-neutral-500">暂无订单。</p>}
          </div>
        </Card>

        <Card>
          <span className="eyebrow">Ledger</span>
          <h2 className="text-sm font-semibold text-white mt-1 mb-4">积分流水</h2>
          <div className="space-y-3">
            {transactions.length ? transactions.slice(0, 8).map(item => (
              <div key={item.id} className="flex justify-between gap-4 text-xs border-b border-neutral-900 pb-3">
                <div>
                  <div className="text-neutral-300">{item.description || item.type}</div>
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
      </div>
    </div>
  );
}
