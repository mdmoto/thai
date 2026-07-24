"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { Input } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [showPass, setShowPass] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    router.push("/dashboard");
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-base">
      <div className="relative w-full max-w-sm mx-4 animate-fade-in-up">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-neutral-900 border border-neutral-800 mb-4">
            <span className="text-sm font-semibold text-white">MT</span>
          </div>
          <h1 className="text-xl font-semibold text-white tracking-tight">Thailand Market Twin</h1>
          <p className="text-sm text-neutral-400 mt-1">泰国数字市场孪生平台</p>
        </div>

        {/* Card */}
        <div className="cmai-card p-6">
          <h2 className="text-base font-semibold text-white mb-6">登录账户</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="邮箱"
              type="email"
              placeholder="请输入邮箱"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
            />
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-neutral-300">密码</label>
              <div className="relative">
                <input
                  type={showPass ? "text" : "password"}
                  className="input-field pr-10"
                  placeholder="请输入密码"
                  required
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  onClick={() => setShowPass(!showPass)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-500 hover:text-neutral-300"
                >
                  {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div className="flex justify-end">
              <Link href="#" className="text-xs text-neutral-400 hover:text-white">忘记密码？</Link>
            </div>

            <button type="submit" className="btn-primary w-full justify-center py-3">
              登录
            </button>
          </form>

          <div className="flex items-center gap-3 my-4">
            <div className="divider flex-1" />
            <span className="text-xs text-neutral-500">或</span>
            <div className="divider flex-1" />
          </div>

          <button className="btn-secondary w-full justify-center py-3 gap-2">
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            使用 Google 登录
          </button>

          <p className="text-xs text-center text-neutral-500 mt-5">
            还没有账号？{" "}
            <Link href="/signup" className="text-white font-medium hover:underline">
              立即注册
            </Link>
          </p>
        </div>

        {/* Trust note */}
        <p className="text-[10px] text-center text-neutral-500 mt-4 px-4">
          本平台使用合成人口模拟，不保证真实市场预测结果。
          <Link href="#" className="text-neutral-400 ml-1 hover:text-white">服务条款</Link>
          <span className="mx-1">·</span>
          <Link href="#" className="text-neutral-400 hover:text-white">隐私政策</Link>
        </p>
      </div>
    </div>
  );
}
