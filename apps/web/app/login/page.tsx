"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Building, Eye, EyeOff, MailCheck, Ticket } from "lucide-react";
import {
  AuthConfig,
  completeRegistrationVerificationApi,
  getAuthConfigApi,
  loginApi,
  registerApi,
  startRegistrationVerificationApi,
} from "@/lib/api-client";
import { saveAuthSession } from "@/lib/auth-session";
import { Input } from "@/components/ui";
import { BrandMark } from "@/components/brand-mark";
import { RegistrationTurnstile } from "@/components/registration-turnstile";

export default function LoginPage() {
  const router = useRouter();
  const [registering, setRegistering] = useState(false);
  const [showPass, setShowPass] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [company, setCompany] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [turnstileToken, setTurnstileToken] = useState("");
  const [turnstileReset, setTurnstileReset] = useState(0);
  const [challengeId, setChallengeId] = useState<string | null>(null);
  const [verificationCode, setVerificationCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAuthConfigApi()
      .then(setAuthConfig)
      .catch(() => setError("注册安全配置加载失败，请稍后刷新页面"));
  }, []);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      let result;
      if (!registering) {
        result = await loginApi({ email, password });
      } else if (challengeId) {
        result = await completeRegistrationVerificationApi({
          challenge_id: challengeId,
          code: verificationCode,
        });
      } else if (authConfig?.email_verification_required) {
        if (!turnstileToken) {
          throw new Error("请先完成人机验证");
        }
        const challenge = await startRegistrationVerificationApi({
          email,
          password,
          name,
          company,
          invite_code: inviteCode || undefined,
          turnstile_token: turnstileToken,
        });
        setChallengeId(challenge.challenge_id);
        setVerificationCode("");
        return;
      } else {
        if (!authConfig) {
          throw new Error("安全配置正在加载，请稍后再试");
        }
        result = await registerApi({
            email,
            password,
            name,
            company,
            invite_code: inviteCode || undefined,
        });
      }
      saveAuthSession(result.user, result.access_token);
      const requested = new URLSearchParams(window.location.search).get("next");
      const destination =
        requested && requested.startsWith("/") && !requested.startsWith("//")
          ? requested
          : "/dashboard";
      router.push(destination);
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
      if (registering && !challengeId) {
        setTurnstileToken("");
        setTurnstileReset(value => value + 1);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-base py-10">
      <div className="w-full max-w-sm mx-4 animate-fade-in-up">
        <Link href="/" className="block text-center mb-8">
          <BrandMark full className="w-64 h-auto mx-auto mb-4" priority />
          <p className="text-sm text-neutral-400">🇹🇭 泰国出海商业沙盘决策平台</p>
        </Link>

        <div className="cmai-card p-6">
          <h2 className="text-base font-semibold text-white mb-2">
            {challengeId
              ? "验证您的工作邮箱"
              : registering
                ? "创建工作区账号"
                : "登录工作区"}
          </h2>
          <p className="text-xs text-neutral-500 mb-6">
            {challengeId
              ? `六位验证码已发送到 ${email}，10 分钟内有效。`
              : registering
              ? "注册即刻免费体验商业沙盘推演；填写有效邀请码直接赠送 5 积分体验包。"
              : "继续访问您保存的商业沙盘评估研报与订单。"}
          </p>

          {error && (
            <div className="p-3 mb-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {challengeId ? (
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-neutral-300">
                  邮箱验证码
                </label>
                <div className="relative">
                  <MailCheck size={15} className="absolute left-3 top-3 text-neutral-500" />
                  <input
                    className="input-field pl-9 text-center tracking-[0.45em] text-lg"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    required
                    pattern="\d{6}"
                    maxLength={6}
                    value={verificationCode}
                    onChange={event =>
                      setVerificationCode(event.target.value.replace(/\D/g, ""))
                    }
                  />
                </div>
              </div>
            ) : registering && (
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
                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-neutral-300">
                    邀请码（选填）
                  </label>
                  <div className="relative">
                    <Ticket size={15} className="absolute left-3 top-3 text-neutral-500" />
                    <input
                      className="input-field pl-9 uppercase"
                      value={inviteCode}
                      onChange={event => setInviteCode(event.target.value.toUpperCase())}
                      placeholder="填写后验证赠送积分"
                      maxLength={64}
                    />
                  </div>
                  <p className="text-[10px] text-neutral-500">
                    邀请码用于记录客户来源；只有有效邀请码会获得体验积分。
                  </p>
                </div>
              </>
            )}
            {!challengeId && (
              <>
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
              </>
            )}
            {registering &&
              !challengeId &&
              authConfig?.email_verification_required &&
              authConfig.turnstile_site_key && (
                <RegistrationTurnstile
                  siteKey={authConfig.turnstile_site_key}
                  onToken={setTurnstileToken}
                  resetNonce={turnstileReset}
                />
              )}
            {challengeId && (
              <button
                type="button"
                onClick={() => {
                  setChallengeId(null);
                  setVerificationCode("");
                  setTurnstileToken("");
                  setTurnstileReset(value => value + 1);
                  setError(null);
                }}
                className="w-full text-xs text-neutral-400 hover:text-white"
              >
                返回修改邮箱或重新发送
              </button>
            )}
            <button
              type="submit"
              disabled={
                loading ||
                Boolean(
                  challengeId &&
                  verificationCode.length !== 6,
                )
              }
              className="btn-primary w-full justify-center py-3"
            >
              {loading
                ? "处理中…"
                : challengeId
                  ? "验证并创建账号"
                  : registering
                    ? authConfig?.email_verification_required
                      ? "发送邮箱验证码"
                      : "注册并进入工作区"
                    : "登录"}
            </button>
          </form>

          <button
            onClick={() => {
              setRegistering(!registering);
              setChallengeId(null);
              setVerificationCode("");
              setTurnstileToken("");
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
