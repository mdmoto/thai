"use client";

import { useState } from "react";
import { X, Zap, Check, CreditCard, QrCode } from "lucide-react";
import { cn } from "@/lib/utils";

interface RechargeModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: any;
  onRechargeSuccess: (newBalance: number) => void;
}

const PACKAGES = [
  {
    id: "pkg_basic",
    name: "体验充值包",
    credits: 100,
    bonus: 0,
    price: "¥99 RMB",
    priceNum: 99,
    desc: "适合初次测试与少量项目预研",
    features: ["支持 5 次 30,000 人专业模拟", "支持 1 次 100,000 人企业深度模拟", "全套 10 维图表报告"]
  },
  {
    id: "pkg_pro",
    name: "专业超值包",
    credits: 500,
    bonus: 100,
    popular: true,
    price: "¥399 RMB",
    priceNum: 399,
    desc: "中小企业出海与品牌评估首选",
    features: ["赠送 100 额外积分 (共 600 积分)", "支持 30 次专业模拟或 7 次企业深度模拟", "Gemini 1.5 Pro 思维链推理", "优先客户支持"]
  },
  {
    id: "pkg_enterprise",
    name: "企业深度包",
    credits: 2000,
    bonus: 500,
    price: "¥1,499 RMB",
    priceNum: 1499,
    desc: "大型集团、咨询机构与多项目复盘",
    features: ["赠送 500 额外积分 (共 2,500 积分)", "支持 30 万超大样本算力引擎", "无限次 Gemini 1.5 Pro 深度推理", "专属客户经理与定制数据导流"]
  }
];

export function RechargeModal({ isOpen, onClose, user, onRechargeSuccess }: RechargeModalProps) {
  const [selectedPkg, setSelectedPkg] = useState(PACKAGES[1]);
  const [paymentStep, setPaymentStep] = useState<"SELECT" | "PAY">("SELECT");
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleConfirmPay = async () => {
    setLoading(true);

    const token = localStorage.getItem("market_twin_token");
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://ai-100282158973.asia-southeast1.run.app";

    try {
      const resp = await fetch(`${API_BASE}/v1/billing/recharge`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          amount: selectedPkg.credits + selectedPkg.bonus,
          payment_ref: `WX_${Date.now()}`
        })
      });

      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || "充值失败");
      }

      onRechargeSuccess(data.credits_balance);
      setPaymentStep("SELECT");
      onClose();
    } catch (e: any) {
      alert(e.message || "充值异常");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fade-in">
      <div className="relative w-full max-w-2xl bg-[#0c0c0c] border border-neutral-800 rounded-2xl p-6 shadow-2xl space-y-6">
        <button
          onClick={() => { setPaymentStep("SELECT"); onClose(); }}
          className="absolute top-4 right-4 text-neutral-500 hover:text-white transition-colors"
        >
          <X size={18} />
        </button>

        <div className="text-center space-y-1">
          <span className="eyebrow">Credits & Billing</span>
          <h2 className="text-xl font-light text-white tracking-tight">
            购买积分与算力额度
          </h2>
          <p className="text-xs text-neutral-400 font-light">
            当前账号: <strong className="text-white">{user?.email || "未登录"}</strong> · 余额: <strong className="text-white font-mono">{user?.credits_balance || 0} 积分</strong>
          </p>
        </div>

        {paymentStep === "SELECT" ? (
          <div className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {PACKAGES.map((pkg) => (
                <div
                  key={pkg.id}
                  onClick={() => setSelectedPkg(pkg)}
                  className={cn(
                    "relative p-4 rounded-xl border cursor-pointer transition-all space-y-3",
                    selectedPkg.id === pkg.id
                      ? "bg-neutral-900 border-white text-white shadow-lg"
                      : "bg-black border-neutral-800 text-neutral-400 hover:border-neutral-700"
                  )}
                >
                  {pkg.popular && (
                    <span className="absolute -top-2.5 right-3 text-[10px] font-mono px-2 py-0.5 rounded-full bg-white text-black font-semibold">
                      最受欢迎
                    </span>
                  )}
                  <div>
                    <div className="text-xs font-semibold text-white">{pkg.name}</div>
                    <div className="text-xl font-light text-white font-mono mt-1">{pkg.price}</div>
                    <div className="text-[10px] text-neutral-400 font-mono mt-0.5">
                      到账 {pkg.credits + pkg.bonus} 积分
                      {pkg.bonus > 0 && ` (含赠送 ${pkg.bonus})`}
                    </div>
                  </div>

                  <p className="text-[11px] text-neutral-400 leading-relaxed font-light">{pkg.desc}</p>

                  <div className="space-y-1.5 pt-2 border-t border-neutral-800 text-[10px]">
                    {pkg.features.map((f, i) => (
                      <div key={i} className="flex items-center gap-1.5 text-neutral-300">
                        <Check size={11} className="text-neutral-400 shrink-0" />
                        <span>{f}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-neutral-900">
              <button onClick={onClose} className="btn-cmai-ghost text-xs">取消</button>
              <button
                onClick={() => setPaymentStep("PAY")}
                className="btn-cmai-primary text-xs px-6 py-2"
              >
                立即支付 {selectedPkg.price}
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-6 text-center py-4">
            <div className="p-4 rounded-xl bg-black border border-neutral-800 inline-block">
              <QrCode size={160} className="text-white mx-auto" />
            </div>

            <div className="space-y-1">
              <div className="text-sm font-semibold text-white">微信 / 支付宝扫码支付</div>
              <div className="text-2xl font-light text-white font-mono">{selectedPkg.price}</div>
              <div className="text-xs text-neutral-400">支付成功后积分自动实时到账</div>
            </div>

            <div className="flex justify-center gap-3 pt-4">
              <button
                onClick={() => setPaymentStep("SELECT")}
                className="btn-cmai-secondary text-xs px-4"
              >
                返回选择套餐
              </button>
              <button
                onClick={handleConfirmPay}
                disabled={loading}
                className="btn-cmai-primary text-xs px-6"
              >
                {loading ? "验证支付中..." : "确认支付已完成 (模拟入账)"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
