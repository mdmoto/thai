"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  CheckCircle2,
  CircleDollarSign,
  ClipboardCheck,
  Loader2,
  RefreshCw,
  Search,
  ShieldAlert,
  Users,
  Workflow,
} from "lucide-react";
import { Card } from "@/components/ui";
import {
  AdminDashboard,
  completeAdminOrderApi,
  getAdminDashboardApi,
  getMeApi,
} from "@/lib/api-client";

const PACKAGE_LABELS: Record<string, string> = {
  BASIC_DECISION_SINGLE: "单次基础决策",
  STARTER: "单次专业决策包",
  GROWTH: "增长团队包",
  SCALE: "规模化决策包",
};

const STATUS_LABELS: Record<string, string> = {
  PENDING_PAYMENT: "待付款",
  PAID: "已确认并入账",
  CANCELLED: "已取消",
  EXPIRED: "已过期",
  FAILED: "处理失败",
};

const AUDIT_LABELS: Record<string, string> = {
  ADMIN_ACCOUNT_PROVISIONED: "创建或更新管理员账号",
  PAYMENT_CONFIRMED: "确认付款并入账",
};

function formatMoney(amountMinor: number): string {
  return `฿${(amountMinor / 100).toLocaleString("zh-CN")}`;
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function StatCard({
  label,
  value,
  note,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  note: string;
  icon: typeof Users;
}) {
  return (
    <Card className="!p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs text-neutral-400">{label}</div>
          <div className="text-2xl font-semibold text-white mt-2 tabular-nums">
            {value}
          </div>
          <div className="text-[11px] text-neutral-500 mt-2">{note}</div>
        </div>
        <div className="w-9 h-9 rounded-xl border border-neutral-800 bg-neutral-950 flex items-center justify-center text-neutral-300">
          <Icon size={17} />
        </div>
      </div>
    </Card>
  );
}

export function AdminClient() {
  const [data, setData] = useState<AdminDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [references, setReferences] = useState<Record<string, string>>({});
  const [completing, setCompleting] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const profile = await getMeApi();
      if (!profile.is_admin) {
        setForbidden(true);
        return;
      }
      setForbidden(false);
      setData(await getAdminDashboardApi());
    } catch (err) {
      setError(err instanceof Error ? err.message : "管理数据读取失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const normalizedQuery = query.trim().toLowerCase();
  const filteredUsers = useMemo(
    () =>
      (data?.users ?? []).filter(user =>
        [
          user.email,
          user.name,
          user.company,
          user.acquisition_source,
        ]
          .filter(Boolean)
          .some(value =>
            String(value).toLowerCase().includes(normalizedQuery),
          ),
      ),
    [data?.users, normalizedQuery],
  );
  const filteredOrders = useMemo(
    () =>
      (data?.orders ?? []).filter(order =>
        [
          order.id,
          order.user_email,
          order.user_name,
          order.company,
          order.payment_reference,
        ]
          .filter(Boolean)
          .some(value =>
            String(value).toLowerCase().includes(normalizedQuery),
          ),
      ),
    [data?.orders, normalizedQuery],
  );

  const completeOrder = async (orderId: string) => {
    const reference = (references[orderId] || "").trim();
    if (reference.length < 4) {
      setError("请填写至少 4 个字符的付款凭证，例如银行流水号。");
      return;
    }
    const confirmed = window.confirm(
      "确认已经实际收到这笔款项吗？确认后系统会立即向客户发放决策次数和赠送积分，且不能重复入账。",
    );
    if (!confirmed) return;
    setCompleting(orderId);
    setError(null);
    try {
      await completeAdminOrderApi(orderId, reference);
      setReferences(current => ({ ...current, [orderId]: "" }));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "付款核销失败");
    } finally {
      setCompleting(null);
    }
  };

  if (loading && !data) {
    return (
      <div className="p-8 flex items-center gap-3 text-sm text-neutral-400">
        <Loader2 size={18} className="animate-spin" /> 正在读取管理数据…
      </div>
    );
  }

  if (forbidden) {
    return (
      <div className="p-5 sm:p-8 max-w-3xl mx-auto">
        <Card className="border-rose-950/70">
          <div className="flex items-start gap-3">
            <ShieldAlert size={20} className="text-rose-300 shrink-0" />
            <div>
              <h1 className="text-base font-semibold text-white">
                当前账号没有管理权限
              </h1>
              <p className="text-sm text-neutral-400 mt-2">
                请使用已指定的管理员邮箱登录。普通客户无法读取其他用户和付款数据。
              </p>
              <Link
                href="/login?next=/admin"
                className="btn-cmai-primary mt-5"
              >
                切换管理员账号
              </Link>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  const overview = data?.overview;

  return (
    <div className="p-5 sm:p-8 max-w-[1500px] mx-auto space-y-8">
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <span className="eyebrow">仅管理员可见</span>
          <h1 className="text-2xl font-semibold text-white mt-2">
            客户与付款管理
          </h1>
          <p className="text-sm text-neutral-400 mt-2 max-w-2xl">
            查看注册客户、套餐订单与运行情况。只有确认实际到账后，才能执行入账。
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <label className="relative">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500"
            />
            <input
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder="搜索邮箱、公司或订单号"
              className="w-full sm:w-72 rounded-lg border border-neutral-800 bg-neutral-950 py-2 pl-9 pr-3 text-xs text-white outline-none focus:border-neutral-600"
            />
          </label>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="btn-cmai-secondary justify-center"
          >
            <RefreshCw
              size={14}
              className={loading ? "animate-spin" : undefined}
            />
            刷新
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-950 bg-rose-950/20 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          label="注册用户"
          value={overview?.total_users ?? 0}
          note="已完成邮箱验证或由管理员创建"
          icon={Users}
        />
        <StatCard
          label="待核销订单"
          value={overview?.pending_orders ?? 0}
          note={`全部订单 ${overview?.total_orders ?? 0} 笔`}
          icon={ClipboardCheck}
        />
        <StatCard
          label="已确认收入"
          value={formatMoney(overview?.paid_revenue_minor ?? 0)}
          note={`已入账 ${overview?.paid_orders ?? 0} 笔`}
          icon={CircleDollarSign}
        />
        <StatCard
          label="模拟任务"
          value={overview?.completed_runs ?? 0}
          note={`总计 ${overview?.total_runs ?? 0} · 失败 ${overview?.failed_runs ?? 0}`}
          icon={Workflow}
        />
      </div>

      <Card className="!p-0 overflow-hidden">
        <div className="px-5 py-4 border-b border-neutral-900 flex items-center justify-between gap-3">
          <div>
            <span className="eyebrow">订单</span>
            <h2 className="text-sm font-semibold text-white mt-1">
              付款核销
            </h2>
          </div>
          <span className="text-xs text-neutral-500">
            显示 {filteredOrders.length} 笔
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1050px] text-xs">
            <thead className="bg-neutral-950 text-neutral-500">
              <tr>
                <th className="text-left font-medium px-5 py-3">订单与客户</th>
                <th className="text-left font-medium px-4 py-3">套餐</th>
                <th className="text-right font-medium px-4 py-3">金额</th>
                <th className="text-left font-medium px-4 py-3">状态</th>
                <th className="text-left font-medium px-4 py-3">创建时间</th>
                <th className="text-left font-medium px-5 py-3">付款操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredOrders.map(order => (
                <tr
                  key={order.id}
                  className="border-t border-neutral-900 align-top"
                >
                  <td className="px-5 py-4">
                    <div className="font-mono text-white">{order.id}</div>
                    <div className="text-neutral-400 mt-1">
                      {order.user_name || "未填写姓名"} · {order.user_email}
                    </div>
                    {order.company && (
                      <div className="text-neutral-600 mt-1">{order.company}</div>
                    )}
                  </td>
                  <td className="px-4 py-4 text-neutral-300">
                    {PACKAGE_LABELS[order.package_code] ?? order.package_code}
                  </td>
                  <td className="px-4 py-4 text-right font-medium text-white tabular-nums">
                    {formatMoney(order.amount_minor)}
                  </td>
                  <td className="px-4 py-4">
                    <span
                      className={
                        order.status === "PAID"
                          ? "text-emerald-300"
                          : "text-amber-300"
                      }
                    >
                      {STATUS_LABELS[order.status] ?? order.status}
                    </span>
                    {order.payment_reference && (
                      <div className="text-neutral-600 font-mono mt-1">
                        {order.payment_reference}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-4 text-neutral-500">
                    {formatDate(order.created_at)}
                  </td>
                  <td className="px-5 py-4">
                    {order.status === "PENDING_PAYMENT" ? (
                      <div className="flex items-center gap-2">
                        <input
                          value={references[order.id] || ""}
                          onChange={event =>
                            setReferences(current => ({
                              ...current,
                              [order.id]: event.target.value,
                            }))
                          }
                          placeholder="银行流水号或收款凭证"
                          className="w-52 rounded-lg border border-neutral-800 bg-black px-3 py-2 text-xs text-white outline-none focus:border-neutral-600"
                        />
                        <button
                          type="button"
                          onClick={() => completeOrder(order.id)}
                          disabled={completing !== null}
                          className="btn-cmai-primary whitespace-nowrap"
                        >
                          {completing === order.id ? (
                            <Loader2 size={13} className="animate-spin" />
                          ) : (
                            <CheckCircle2 size={13} />
                          )}
                          确认到账
                        </button>
                      </div>
                    ) : (
                      <span className="text-neutral-600">已完成</span>
                    )}
                  </td>
                </tr>
              ))}
              {!filteredOrders.length && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-5 py-10 text-center text-neutral-600"
                  >
                    暂无匹配订单。
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="!p-0 overflow-hidden">
        <div className="px-5 py-4 border-b border-neutral-900 flex items-center justify-between gap-3">
          <div>
            <span className="eyebrow">客户</span>
            <h2 className="text-sm font-semibold text-white mt-1">
              注册用户
            </h2>
          </div>
          <span className="text-xs text-neutral-500">
            显示 {filteredUsers.length} 人
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1000px] text-xs">
            <thead className="bg-neutral-950 text-neutral-500">
              <tr>
                <th className="text-left font-medium px-5 py-3">用户</th>
                <th className="text-left font-medium px-4 py-3">来源</th>
                <th className="text-right font-medium px-4 py-3">积分</th>
                <th className="text-right font-medium px-4 py-3">基础/深度</th>
                <th className="text-right font-medium px-4 py-3">订单</th>
                <th className="text-right font-medium px-4 py-3">已付款</th>
                <th className="text-left font-medium px-5 py-3">注册时间</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map(user => (
                <tr key={user.id} className="border-t border-neutral-900">
                  <td className="px-5 py-4">
                    <div className="text-white">
                      {user.name || "未填写姓名"}
                      {user.is_admin && (
                        <span className="ml-2 text-[10px] text-blue-300">
                          管理员
                        </span>
                      )}
                    </div>
                    <div className="text-neutral-400 mt-1">{user.email}</div>
                    {user.company && (
                      <div className="text-neutral-600 mt-1">{user.company}</div>
                    )}
                  </td>
                  <td className="px-4 py-4 text-neutral-400">
                    {user.acquisition_source || "ORGANIC"}
                    <div className="text-neutral-600 mt-1">
                      邀请码：{user.invite_status || "NOT_PROVIDED"}
                    </div>
                  </td>
                  <td className="px-4 py-4 text-right text-white tabular-nums">
                    {user.credits_balance}
                  </td>
                  <td className="px-4 py-4 text-right text-neutral-300 tabular-nums">
                    {user.basic_decision_runs_balance} /{" "}
                    {user.deep_decision_runs_balance}
                  </td>
                  <td className="px-4 py-4 text-right text-neutral-300 tabular-nums">
                    {user.order_count}
                  </td>
                  <td className="px-4 py-4 text-right text-emerald-300 tabular-nums">
                    {formatMoney(user.paid_total_minor)}
                  </td>
                  <td className="px-5 py-4 text-neutral-500">
                    {formatDate(user.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <span className="eyebrow">安全记录</span>
        <h2 className="text-sm font-semibold text-white mt-1 mb-4">
          最近管理操作
        </h2>
        <div className="space-y-3">
          {(data?.audit_logs ?? []).map(log => (
            <div
              key={log.id}
              className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-neutral-900 pb-3 text-xs"
            >
              <div>
                <div className="text-neutral-300">
                  {AUDIT_LABELS[log.action] ?? log.action}
                </div>
                <div className="text-neutral-600 mt-1 font-mono">
                  {log.target_id} · 操作人 {log.actor_email}
                </div>
              </div>
              <div className="text-neutral-500">
                {formatDate(log.created_at)}
              </div>
            </div>
          ))}
          {!data?.audit_logs.length && (
            <p className="text-xs text-neutral-600">暂无管理操作记录。</p>
          )}
        </div>
      </Card>
    </div>
  );
}
