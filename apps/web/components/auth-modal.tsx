"use client";

import { useState } from "react";
import { X, Lock, Mail, User, Building, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (user: any, token: string) => void;
}

export function AuthModal({ isOpen, onClose, onSuccess }: AuthModalProps) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [company, setCompany] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://ai-100282158973.asia-southeast1.run.app";
    const endpoint = isLogin ? `${API_BASE}/v1/auth/login` : `${API_BASE}/v1/auth/register`;

    try {
      const resp = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(isLogin ? { email, password } : { email, password, name, company }),
      });

      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || "操作失败，请重试");
      }

      localStorage.setItem("market_twin_token", data.access_token);
      localStorage.setItem("market_twin_user", JSON.stringify(data.user));
      onSuccess(data.user, data.access_token);
      onClose();
    } catch (err: any) {
      setError(err.message || "登录/注册失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fade-in">
      <div className="relative w-full max-w-md bg-[#0c0c0c] border border-neutral-800 rounded-2xl p-6 shadow-2xl space-y-6">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-neutral-500 hover:text-white transition-colors"
        >
          <X size={18} />
        </button>

        <div className="text-center space-y-1">
          <span className="eyebrow">Thailand Market Twin Account</span>
          <h2 className="text-xl font-light text-white tracking-tight">
            {isLogin ? "登录您的商业账号" : "注册新账号 (送 50 初始积分)"}
          </h2>
          <p className="text-xs text-neutral-400 font-light">
            {isLogin ? "登录后可保存报告与管理积分额度" : "注册即赠送 50 体验积分，可直接运行 2 次高精度模拟"}
          </p>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-light">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {!isLogin && (
            <>
              <div className="space-y-1">
                <label className="text-[11px] text-neutral-400 font-mono">您的姓名</label>
                <div className="relative">
                  <User size={15} className="absolute left-3 top-3 text-neutral-500" />
                  <input
                    type="text"
                    required
                    placeholder="张经理"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="input-cmai pl-9"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-neutral-400 font-mono">公司/品牌名称 (选填)</label>
                <div className="relative">
                  <Building size={15} className="absolute left-3 top-3 text-neutral-500" />
                  <input
                    type="text"
                    placeholder="曼谷餐饮管理有限公司"
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    className="input-cmai pl-9"
                  />
                </div>
              </div>
            </>
          )}

          <div className="space-y-1">
            <label className="text-[11px] text-neutral-400 font-mono">工作邮箱</label>
            <div className="relative">
              <Mail size={15} className="absolute left-3 top-3 text-neutral-500" />
              <input
                type="email"
                required
                placeholder="name@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input-cmai pl-9"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-[11px] text-neutral-400 font-mono">密码</label>
            <div className="relative">
              <Lock size={15} className="absolute left-3 top-3 text-neutral-500" />
              <input
                type="password"
                required
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-cmai pl-9"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full btn-cmai-primary py-2.5 text-xs font-semibold mt-2"
          >
            {loading ? "处理中..." : isLogin ? "立即登录" : "注册并领取 50 积分"}
            <ArrowRight size={14} className="ml-1" />
          </button>
        </form>

        <div className="text-center pt-2 border-t border-neutral-900">
          <button
            onClick={() => { setIsLogin(!isLogin); setError(""); }}
            className="text-xs text-neutral-400 hover:text-white transition-colors"
          >
            {isLogin ? "还没有账号？点击注册新账号" : "已有账号？点击直接登录"}
          </button>
        </div>
      </div>
    </div>
  );
}
