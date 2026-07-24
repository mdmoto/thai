"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Building, Eye, EyeOff } from "lucide-react";
import { loginApi, registerApi } from "@/lib/api-client";
import { saveAuthSession } from "@/lib/auth-session";
import { Input } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [registering, setRegistering] = useState(false);
  const [showPass, setShowPass] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [company, setCompany] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = registering
        ? await registerApi({ email, password, name, company })
        : await loginApi({ email, password });
      saveAuthSession(result.user, result.access_token);
      const requested = new URLSearchParams(window.location.search).get("next");
      const destination =
        requested && requested.startsWith("/") && !requested.startsWith("//")
          ? requested
          : "/dashboard";
      router.push(destination);
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-base py-10">
      <div className="w-full max-w-sm mx-4 animate-fade-in-up">
        <Link href="/" className="block text-center mb-8">
          <div className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-neutral-900 border border-neutral-800 mb-4">
            <span className="text-sm font-semibold text-white">MT</span>
          </div>
          <h1 className="text-xl font-semibold text-white tracking-tight">
            Thailand Market Twin
          </h1>
          <p className="text-sm text-neutral-400 mt-1">泰国消费品决策平台</p>
        </Link>

        <div className="cmai-card p-6">
          <h2 className="text-base font-semibold text-white mb-2">
            {registering ? "创建工作区账号" : "登录工作区"}
          </h2>
          <p className="text-xs text-neutral-500 mb-6">
            {registering
              ? "注册赠送 5 积分，可运行一次 Standard 体验。"
              : "继续访问您保存的项目、报告和订单。"}
          </p>

          {error && (
            <div className="p-3 mb-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {registering && (
              <>
                <Input
                  label="姓名"
                  required
                  value={name}
                  onChange={event => setName(event.target.value)}
                />
                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-neutral-300">
                    公司或品牌（选填）
                  </label>
                  <div className="relative">
                    <Building size={15} className="absolute left-3 top-3 text-neutral-500" />
                    <input
                      className="input-field pl-9"
                      value={company}
                      onChange={event => setCompany(event.target.value)}
                    />
                  </div>
                </div>
              </>
            )}
            <Input
              label="工作邮箱"
              type="email"
              required
              value={email}
              onChange={event => setEmail(event.target.value)}
            />
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-neutral-300">密码</label>
              <div className="relative">
                <input
                  type={showPass ? "text" : "password"}
                  className="input-field pr-10"
                  required
                  minLength={registering ? 10 : 1}
                  value={password}
                  onChange={event => setPassword(event.target.value)}
                />
                <button
                  type="button"
                  aria-label={showPass ? "隐藏密码" : "显示密码"}
                  onClick={() => setShowPass(!showPass)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-500 hover:text-neutral-300"
                >
                  {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {registering && (
                <p className="text-[10px] text-neutral-500">至少 10 个字符</p>
              )}
            </div>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full justify-center py-3"
            >
              {loading ? "处理中…" : registering ? "注册并进入工作区" : "登录"}
            </button>
          </form>

          <button
            onClick={() => {
              setRegistering(!registering);
              setError(null);
            }}
            className="w-full text-xs text-neutral-400 hover:text-white mt-5"
          >
            {registering ? "已有账号？返回登录" : "没有账号？创建账号"}
          </button>
        </div>

        <p className="text-[10px] text-center text-neutral-500 mt-4 px-4">
          继续使用即表示同意
          <Link href="/terms" className="text-neutral-300 mx-1">服务条款</Link>
          与
          <Link href="/privacy" className="text-neutral-300 ml-1">隐私说明</Link>
        </p>
      </div>
    </div>
  );
}
