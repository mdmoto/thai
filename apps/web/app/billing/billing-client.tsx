"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowUpRight,
  Check,
  Clock3,
  Loader2,
  QrCode,
  Send,
} from "lucide-react";
import {
  BillingPackage,
  createOrderApi,
  getCatalogApi,
  getEntitlementTransactionsApi,
  getMeApi,
  getOrdersApi,
  getTransactionsApi,
  PaymentMethod,
  PurchaseOrder,
  submitPaymentClaimApi,
  UserProfile,
} from "@/lib/api-client";
import { Card } from "@/components/ui";
import { parseApiDate } from "@/lib/utils";

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
  PENDING_PAYMENT: "待扫码付款",
  PAYMENT_REVIEW: "等待人工核验",
  PAYMENT_REJECTED: "付款信息需补充",
  PAID: "已核验并入账",
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
  const [selectedMethod, setSelectedMethod] = useState<
    PaymentMethod["code"] | null
  >(null);
  const [payerName, setPayerName] = useState("");
  const [paymentTime, setPaymentTime] = useState("");
  const [claimReference, setClaimReference] = useState("");
  const [claimNote, setClaimNote] = useState("");
  const [qrLoaded, setQrLoaded] = useState<Record<string, boolean>>({});
  const [submittingClaim, setSubmittingClaim] = useState(false);
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
      setSelectedMethod(order.allowed_payment_methods[0]?.code ?? null);
      setPayerName(user?.name || "");
      setPaymentTime("");
      setClaimReference("");
      setClaimNote("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建订单失败");
    } finally {
      setCreating(null);
    }
  };

  const openOrder = (order: PurchaseOrder) => {
    setCreatedOrder(order);
    setSelectedMethod(
      order.payment_method ??
        order.allowed_payment_methods[0]?.code ??
        null,
    );
    setPayerName(order.payer_name || user?.name || "");
    setPaymentTime(order.payment_time_text || "");
    setClaimReference(order.payment_claim_reference || "");
    setClaimNote(order.payment_claim_note || "");
    setError(null);
  };

  const submitPaymentClaim = async () => {
    if (!createdOrder || !selectedMethod) return;
    if (!qrLoaded[selectedMethod]) {
      setError("正式收款码尚未配置，请先联系官方客服，不要向其他二维码付款。");
      return;
    }
    if (payerName.trim().length < 2) {
      setError("请填写付款人姓名，方便人工核对到账记录。");
      return;
    }
    if (!paymentTime) {
      setError("请选择大致付款时间，方便人工核对到账记录。");
      return;
    }
    setSubmittingClaim(true);
    setError(null);
    try {
      const updated = await submitPaymentClaimApi(createdOrder.id, {
        payment_method: selectedMethod,
        payer_name: payerName.trim(),
        payment_claim_reference: claimReference.trim() || undefined,
        payment_time_text: paymentTime,
        note: claimNote.trim() || undefined,
      });
      setCreatedOrder(updated);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "付款信息提交失败");
    } finally {
      setSubmittingClaim(false);
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
            创建订单后使用页面上的固定收款码付款，再提交付款人和时间。
            当前没有自动回调，只有人工确认实际到账后才会发放次数和赠送积分。
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
              {createdOrder.status === "PAID" ? (
                <Check size={15} />
              ) : (
                <QrCode size={15} />
              )}
            </div>
            <div className="flex-1">
              <h2 className="text-sm font-semibold text-white">
                {createdOrder.status === "PAID"
                  ? "订单已核验并入账"
                  : createdOrder.status === "PAYMENT_REVIEW"
                    ? "付款信息已提交"
                    : "请使用固定收款码付款"}
              </h2>
              <p className="text-xs text-neutral-400 mt-1">
                订单编号 <span className="font-mono text-white">{createdOrder.id}</span>。
                金额 <span className="text-white">฿{(createdOrder.amount_minor / 100).toLocaleString()}</span>。
              </p>
              {createdOrder.review_note && createdOrder.status === "PAYMENT_REJECTED" && (
                <p className="mt-3 rounded-lg border border-amber-900/60 bg-amber-950/20 px-3 py-2 text-xs text-amber-200">
                  核验说明：{createdOrder.review_note}
                </p>
              )}

              {createdOrder.status === "PAYMENT_REVIEW" ? (
                <div className="mt-4 rounded-xl border border-amber-900/50 bg-amber-950/10 p-4">
                  <div className="flex items-center gap-2 text-sm text-amber-200">
                    <Clock3 size={15} />
                    正在等待人工核验
                  </div>
                  <p className="text-xs text-neutral-500 mt-2">
                    核验前不会发放次数或积分。请勿重复付款；如需补充信息可联系官方客服。
                  </p>
                </div>
              ) : createdOrder.status !== "PAID" ? (
                <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(320px,420px)_1fr]">
                  <div>
                    <div className="flex flex-wrap gap-2 mb-3">
                      {createdOrder.allowed_payment_methods.map(method => (
                        <button
                          key={method.code}
                          type="button"
                          onClick={() => setSelectedMethod(method.code)}
                          className={
                            selectedMethod === method.code
                              ? "rounded-lg border border-white bg-white px-3 py-2 text-xs text-black"
                              : "rounded-lg border border-neutral-800 bg-black px-3 py-2 text-xs text-neutral-300"
                          }
                        >
                          {method.name}
                        </button>
                      ))}
                    </div>
                    {createdOrder.allowed_payment_methods
                      .filter(method => method.code === selectedMethod)
                      .map(method => (
                        <div key={method.code}>
                          <a
                            href={method.image_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            aria-label={`打开大图查看${method.name}`}
                            className="block rounded-xl border border-neutral-800 bg-white p-2 overflow-hidden"
                          >
                            <img
                              src={method.image_url}
                              alt={method.name}
                              className="mx-auto w-full max-h-[620px] object-contain"
                              onLoad={() =>
                                setQrLoaded(current => ({
                                  ...current,
                                  [method.code]: true,
                                }))
                              }
                              onError={() =>
                                setQrLoaded(current => ({
                                  ...current,
                                  [method.code]: false,
                                }))
                              }
                            />
                          </a>
                          {qrLoaded[method.code] && (
                            <p className="mt-2 text-center text-[11px] text-neutral-500">
                              扫码困难时，点击图片打开清晰大图
                            </p>
                          )}
                          {!qrLoaded[method.code] && (
                            <div className="mt-3 flex gap-2 rounded-lg border border-amber-900/50 bg-amber-950/20 p-3 text-xs text-amber-200">
                              <AlertTriangle size={15} className="shrink-0" />
                              正式收款码暂未配置。请勿向其他二维码付款，先联系官方客服。
                            </div>
                          )}
                        </div>
                      ))}
                  </div>
                  <div className="space-y-3">
                    <div>
                      <label className="text-xs text-neutral-400">付款人姓名 *</label>
                      <input
                        value={payerName}
                        onChange={event => setPayerName(event.target.value)}
                        placeholder="请填写付款账户显示的姓名"
                        className="mt-1 w-full rounded-lg border border-neutral-800 bg-black px-3 py-2.5 text-sm text-white outline-none focus:border-neutral-600"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-neutral-400">大致付款时间 *</label>
                      <input
                        type="datetime-local"
                        value={paymentTime}
                        onChange={event => setPaymentTime(event.target.value)}
                        className="mt-1 w-full rounded-lg border border-neutral-800 bg-black px-3 py-2.5 text-sm text-white outline-none focus:border-neutral-600"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-neutral-400">交易单号后几位（可选）</label>
                      <input
                        value={claimReference}
                        onChange={event => setClaimReference(event.target.value)}
                        placeholder="例如：最后 6 位"
                        className="mt-1 w-full rounded-lg border border-neutral-800 bg-black px-3 py-2.5 text-sm text-white outline-none focus:border-neutral-600"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-neutral-400">备注（可选）</label>
                      <input
                        value={claimNote}
                        onChange={event => setClaimNote(event.target.value)}
                        placeholder="例如：公司账户付款"
                        className="mt-1 w-full rounded-lg border border-neutral-800 bg-black px-3 py-2.5 text-sm text-white outline-none focus:border-neutral-600"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={submitPaymentClaim}
                      disabled={
                        submittingClaim ||
                        !selectedMethod ||
                        !qrLoaded[selectedMethod]
                      }
                      className="btn-cmai-primary w-full"
                    >
                      {submittingClaim ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <Send size={14} />
                      )}
                      我已付款，提交人工核验
                    </button>
                  </div>
                </div>
              ) : (
                <p className="mt-4 text-xs text-emerald-300">
                  决策次数和赠送积分已经发放，可返回项目页面开始运行。
                </p>
              )}
              <a
                href={salesUrlForOrder(createdOrder)}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-cmai-secondary mt-4"
              >
                付款遇到问题，联系官方客服 <ArrowUpRight size={14} />
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
                  {order.status !== "PAID" && (
                    <button
                      type="button"
                      onClick={() => openOrder(order)}
                      className="text-blue-300 mt-2 hover:text-blue-200"
                    >
                      {order.status === "PAYMENT_REVIEW" ? "查看核验状态" : "继续付款"}
                    </button>
                  )}
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
                    {parseApiDate(item.created_at).toLocaleString()}
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
                    {PACKAGE_LABELS[item.plan_code] ?? item.plan_code} · {parseApiDate(item.created_at).toLocaleString()}
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
