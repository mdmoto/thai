"use client";

import { useEffect, useState } from "react";
import { X, Lock, Mail, User, Building, ArrowRight, Ticket, MailCheck } from "lucide-react";
import {
  AuthConfig,
  completeRegistrationVerificationApi,
  getAuthConfigApi,
  loginApi,
  registerApi,
  startRegistrationVerificationApi,
  UserProfile,
} from "@/lib/api-client";
import { saveAuthSession } from "@/lib/auth-session";
import { BrandMark } from "@/components/brand-mark";
import { RegistrationTurnstile } from "@/components/registration-turnstile";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (user: UserProfile, token: string) => void;
}

export function AuthModal({ isOpen, onClose, onSuccess }: AuthModalProps) {
  const [isLogin, setIsLogin] = useState(true);
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
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    getAuthConfigApi()
      .then(setAuthConfig)
      .catch(() => setError("注册安全配置加载失败，请稍后重试"));
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      let data;
      if (isLogin) {
        data = await loginApi({ email, password });
      } else if (challengeId) {
        data = await completeRegistrationVerificationApi({
          challenge_id: challengeId,
          code: verificationCode,
        });
      } else if (authConfig?.email_verification_required) {
        if (!turnstileToken) throw new Error("请先完成人机验证");
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
        if (!authConfig) throw new Error("安全配置正在加载，请稍后再试");
        data = await registerApi({
            email,
            password,
            name,
            company,
            invite_code: inviteCode || undefined,
        });
      }
      saveAuthSession(data.user, data.access_token);
      onSuccess(data.user, data.access_token);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录/注册失败");
      if (!isLogin && !challengeId) {
        setTurnstileToken("");
        setTurnstileReset(value => value + 1);
      }
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
          <BrandMark full className="w-48 h-auto mx-auto mb-4" />
          <span className="eyebrow">Chiang Mai AI Center 商业账号</span>
          <h2 className="text-xl font-light text-white tracking-tight">
            {challengeId
              ? "验证您的工作邮箱"
              : isLogin
                ? "登录您的商业账号"
                : "注册新账号"}
          </h2>
          <p className="text-xs text-neutral-400 font-light">
            {challengeId
              ? `验证码已发送到 ${email}，10 分钟内有效`
              : isLogin
                ? "登录后可保存项目、报告和订单"
                : "有效邀请码赠送 5 积分；未填写时初始积分为 0"}
          </p>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-light">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {challengeId ? (
            <div className="space-y-1">
              <label className="text-[11px] text-neutral-400 font-mono">六位邮箱验证码</label>
              <div className="relative">
                <MailCheck size={15} className="absolute left-3 top-3 text-neutral-500" />
                <input
                  className="input-cmai pl-9 text-center tracking-[0.45em] text-lg"
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
          ) : !isLogin && (
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
                    placeholder="您的公司名称"
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    className="input-cmai pl-9"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-neutral-400 font-mono">邀请码（选填）</label>
                <div className="relative">
                  <Ticket size={15} className="absolute left-3 top-3 text-neutral-500" />
                  <input
                    type="text"
                    placeholder="用于记录客户来源"
                    value={inviteCode}
                    onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                    className="input-cmai pl-9 uppercase"
                    maxLength={64}
                  />
                </div>
                <p className="text-[10px] text-neutral-500">只有有效邀请码会获得体验积分。</p>
              </div>
            </>
          )}

          {!challengeId && (
            <>
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
                    minLength={isLogin ? 1 : 10}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="input-cmai pl-9"
                  />
                </div>
              </div>
            </>
          )}

          {!isLogin &&
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
                setError("");
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
              Boolean(challengeId && verificationCode.length !== 6)
            }
            className="w-full btn-cmai-primary py-2.5 text-xs font-semibold mt-2"
          >
            {loading
              ? "处理中..."
              : challengeId
                ? "验证并创建账号"
                : isLogin
                  ? "立即登录"
                  : authConfig?.email_verification_required
                    ? "发送邮箱验证码"
                    : "注册账号"}
            <ArrowRight size={14} className="ml-1" />
          </button>
        </form>

        <div className="text-center pt-2 border-t border-neutral-900">
          <button
            onClick={() => {
              setIsLogin(!isLogin);
              setChallengeId(null);
              setVerificationCode("");
              setTurnstileToken("");
              setError("");
            }}
            className="text-xs text-neutral-400 hover:text-white transition-colors"
          >
            {isLogin ? "还没有账号？点击注册新账号" : "已有账号？点击直接登录"}
          </button>
        </div>
      </div>
    </div>
  );
}
