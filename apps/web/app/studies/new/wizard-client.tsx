"use client";

import { useState, useCallback, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Check, ChevronRight, ImagePlus, Plus, X, Link as LinkIcon } from "lucide-react";
import { STUDY_TYPE_META, PLAN_META, TEMPLATES } from "@/lib/product-catalog";
import { getStoredToken, getStoredUser } from "@/lib/auth-session";
import { Card, Input } from "@/components/ui";
import { cn } from "@/lib/utils";

type StudyType = keyof typeof STUDY_TYPE_META;
type PlanCode = keyof typeof PLAN_META;
type CountryCode = "TH" | "MY";

interface WizardState {
  country_code: CountryCode;
  study_type: StudyType | null;
  name: string;
  description: string;
  product_name: string;
  product_image_data_url: string;
  category: string;
  price: string;
  reference_price: string;
  variable_cost: string;
  selling_points: string[];
  competitors: string[];
  url: string;
  research_urls: string[];
  plan_code: PlanCode;
  business_questions: string[];
  venue_type: string;
  location_text: string;
  average_check: string;
  capacity: string;
  opening_hours: string;
  creative_format: string;
  channel: string;
  creative_content: string;
  preset_scenarios: Array<Record<string, unknown>>;
  template_key: string;
  marketplaces: string[];
  shipping_fee: string;
  delivery_days: string;
  cod_available: boolean;
  official_store: boolean;
  venue_history_text: string;
}

const INIT_STATE: WizardState = {
  country_code: "TH",
  study_type: null,
  name: "",
  description: "",
  product_name: "",
  product_image_data_url: "",
  category: "GENERIC_CONSUMER_PRODUCT",
  price: "",
  reference_price: "",
  variable_cost: "",
  selling_points: [""],
  competitors: [""],
  url: "",
  research_urls: [""],
  plan_code: "STANDARD",
  business_questions: [],
  venue_type: "RESTAURANT",
  location_text: "",
  average_check: "",
  capacity: "",
  opening_hours: "",
  creative_format: "IMAGE",
  channel: "META",
  creative_content: "",
  preset_scenarios: [],
  template_key: "",
  marketplaces: ["Shopee", "Lazada", "TikTok Shop"],
  shipping_fee: "0",
  delivery_days: "4",
  cod_available: true,
  official_store: false,
  venue_history_text: "",
};

function parseVenueHistory(value: string) {
  return value
    .split(/\n+/)
    .map(line => line.trim())
    .filter(Boolean)
    .map(line => line.split(/[,，\t]+/).map(item => item.trim()))
    .map(parts => {
      if (/^\d{4}-\d{1,2}-\d{1,2}$/.test(parts[0] || "")) {
        return {
          date: parts[0],
          hour: Number(String(parts[1] || "").replace(/:00$/, "")),
          visits: Number(parts[2]),
          service_minutes: parts[3] ? Number(parts[3]) : undefined,
        };
      }
      return {
        location_label: parts[0],
        average_daily_visits: Number(parts[1]),
      };
    })
    .filter(row => (
      ("visits" in row && Number.isFinite(row.visits))
      || ("average_daily_visits" in row && Number.isFinite(row.average_daily_visits))
    ));
}

async function compressImageForStudy(file: File): Promise<string> {
  if (!file.type.startsWith("image/")) {
    throw new Error("请上传 JPG、PNG 或 WebP 格式的图片。");
  }
  if (file.size > 12 * 1024 * 1024) {
    throw new Error("图片不能超过 12MB。");
  }
  const bitmap = await createImageBitmap(file);
  const longestSide = Math.max(bitmap.width, bitmap.height);
  const scale = Math.min(1, 1200 / longestSide);
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(bitmap.width * scale));
  canvas.height = Math.max(1, Math.round(bitmap.height * scale));
  canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const dataUrl = canvas.toDataURL("image/jpeg", 0.8);
  if (dataUrl.length > 780_000) {
    throw new Error("图片压缩后仍过大，请裁剪后重新上传。");
  }
  return dataUrl;
}

const BUSINESS_QUESTIONS = {
  PRODUCT_VALIDATION: [
    "哪个价格点转化率最高？",
    "最适合的目标人群是谁？",
    "主要购买阻力是什么？",
    "哪个渠道最适合推广？",
    "与竞品相比优势和劣势？",
  ],
  PRICING_STUDY: [
    "哪个价格收入最大化？",
    "哪个价格毛利最大化？",
    "价格敏感人群占比多少？",
    "提价对转化率影响多少？",
  ],
  VENUE_STUDY: [
    "核心到店客群是谁？",
    "客单价是否适合该客群？",
    "主要到店阻力是什么？",
    "哪种经营情景更值得实测？",
  ],
  SITE_COMPARISON: [
    "哪个候选点位的相对表现最好？",
    "目标客群覆盖差异有多大？",
    "出行与竞品阻力分别是什么？",
  ],
  CREATIVE_TEST: [
    "哪套素材最容易被理解？",
    "哪套素材的信任与行动倾向更高？",
    "主要误解和拒绝原因是什么？",
  ],
  OPERATING_SCENARIO: [
    "营业时间如何影响到店机会？",
    "容量和服务配置的主要风险是什么？",
    "哪个经营方案更值得线下试运行？",
  ],
  DEFAULT: [
    "最适合的目标人群是谁？",
    "主要风险点是什么？",
    "与竞品相比如何？",
    "最优方案是哪个？",
    "如何提高转化率？",
  ],
};

function getQuestions(type: StudyType | null) {
  if (!type) return BUSINESS_QUESTIONS.DEFAULT;
  return BUSINESS_QUESTIONS[type as keyof typeof BUSINESS_QUESTIONS] ?? BUSINESS_QUESTIONS.DEFAULT;
}

export function NewStudyWizard() {
  const router = useRouter();
  const params = useSearchParams();
  const typeParam = params.get("type");
  const initialType = typeParam && typeParam in STUDY_TYPE_META ? typeParam as StudyType : null;
  const initialCategory = params.get("category");
  const initialTemplate = TEMPLATES.find(item => item.id === params.get("template"));
  const templateDefaults = (initialTemplate?.defaults || {}) as Partial<WizardState> & {
    scenarios?: Array<Record<string, unknown>>;
  };

  const [step, setStep] = useState(initialType ? 2 : 1);
  const [state, setState] = useState<WizardState>({
    ...INIT_STATE,
    ...templateDefaults,
    study_type: initialType,
    category: initialType && ["PRODUCT_VALIDATION", "PRICING_STUDY", "CREATIVE_TEST"].includes(initialType)
      ? initialCategory || INIT_STATE.category
      : INIT_STATE.category,
    venue_type: templateDefaults.venue_type || initialCategory || INIT_STATE.venue_type,
    selling_points: templateDefaults.selling_points || INIT_STATE.selling_points,
    preset_scenarios: templateDefaults.scenarios || INIT_STATE.preset_scenarios,
    template_key: initialTemplate?.key === "ecommerce"
      ? "ECOMMERCE"
      : initialTemplate?.key?.toUpperCase() || "",
  });

  const update = useCallback((updates: Partial<WizardState>) => {
    setState(prev => ({ ...prev, ...updates }));
  }, []);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState<boolean | null>(null);
  const [returnPath, setReturnPath] = useState("/studies/new");

  useEffect(() => {
    const user = getStoredUser();
    setAuthReady(Boolean(getStoredToken()));
    // A first-time account should land on its included free preview rather
    // than on a paid simulation it cannot run yet. Preserve an explicit plan
    // choice (for example, a template or a user selection).
    if ((user?.free_preview_runs_balance ?? 0) > 0) {
      setState(current => (
        current.plan_code === INIT_STATE.plan_code
          ? { ...current, plan_code: "PREVIEW" }
          : current
      ));
    }
    setReturnPath(`${window.location.pathname}${window.location.search}`);
  }, []);

  const handleSubmit = async () => {
    if (submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      // 1. Call real FastAPI backend to create study
      const { createStudyApi, confirmStudyApi } = await import("@/lib/api-client");
      const isOffline = Boolean(
        state.study_type
        && ["VENUE_STUDY", "SITE_COMPARISON", "OPERATING_SCENARIO"].includes(state.study_type),
      );
      const candidateLocations = state.study_type === "SITE_COMPARISON"
        ? state.location_text.split(/[;\n、]+/).map(value => value.trim()).filter(Boolean)
        : [];
      const study = await createStudyApi({
        name: state.name || "未命名研究项目",
        study_type: state.study_type || "PRODUCT_VALIDATION",
        country_code: state.country_code,
        plan_code: state.plan_code,
        template_key: state.template_key || undefined,
        product_name: state.product_name,
        product_image_data_url: state.product_image_data_url || undefined,
        category: state.category,
        price: state.price ? Number(state.price) : undefined,
        reference_price: state.reference_price ? Number(state.reference_price) : undefined,
        variable_cost: state.variable_cost ? Number(state.variable_cost) : undefined,
        url: state.url,
        research_urls: state.research_urls.filter(Boolean),
        description: state.description,
        selling_points: state.selling_points.filter(Boolean),
        competitors: state.competitors.filter(Boolean),
        business_questions: state.business_questions,
        venue_type: isOffline ? state.venue_type : undefined,
        average_check: state.average_check ? Number(state.average_check) : undefined,
        capacity: state.capacity ? Number(state.capacity) : undefined,
        opening_hours: state.opening_hours || undefined,
        creative_format: state.study_type === "CREATIVE_TEST" ? state.creative_format : undefined,
        channel: state.study_type === "CREATIVE_TEST" ? state.channel : undefined,
        location: isOffline && state.study_type !== "SITE_COMPARISON" && state.location_text
          ? {
              label: state.location_text,
            }
          : undefined,
        candidate_locations: candidateLocations.map(label => ({ label })),
        venue_history: isOffline
          ? parseVenueHistory(state.venue_history_text)
          : undefined,
        scenarios: candidateLocations.length
          ? candidateLocations.map(label => ({
              name: label,
              price: Number(state.average_check),
            }))
          : state.preset_scenarios,
        marketplaces: state.template_key === "ECOMMERCE" ? state.marketplaces : undefined,
        shipping_fee: state.template_key === "ECOMMERCE" ? Number(state.shipping_fee) : undefined,
        delivery_days: state.template_key === "ECOMMERCE" ? Number(state.delivery_days) : undefined,
        cod_available: state.template_key === "ECOMMERCE" ? state.cod_available : undefined,
        official_store: state.template_key === "ECOMMERCE" ? state.official_store : undefined,
      });

      // 2. Confirm study facts
      await confirmStudyApi(study.id);

      // 3. Redirect to real-time run execution page
      router.push(`/studies/run?id=${encodeURIComponent(study.id)}&plan=${encodeURIComponent(state.plan_code)}`);
    } catch (err) {
      console.error("API submission error:", err);
      setSubmitError(
        err instanceof Error ? err.message : "研究提交失败，请检查后重试。",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const STEPS = [
    { label: "研究选型" },
    { label: "资料填写" },
    { label: "假设确认" },
    { label: "商业问题" },
    { label: "分析方式" },
  ];

  if (authReady === null) {
    return <div className="p-8 text-xs text-neutral-400">正在检查工作区登录状态…</div>;
  }

  if (!authReady) {
    return (
      <div className="max-w-xl mx-auto p-8">
        <Card>
          <div className="eyebrow mb-2">需要登录工作区</div>
          <h2 className="text-lg font-semibold text-white">登录后创建研究</h2>
          <p className="text-sm text-neutral-400 mt-2">
            项目输入、报告和积分都会保存在您的独立工作区中。
          </p>
          <Link
            href={`/login?next=${encodeURIComponent(returnPath)}`}
            className="btn-cmai-primary mt-5"
          >
            登录 / 注册
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-8">
      {/* Steps indicator */}
      <div className="flex items-center gap-2 pb-6 border-b border-neutral-900">
        {STEPS.map((s, i) => {
          const num = i + 1;
          const done = step > num;
          const active = step === num;
          return (
            <div key={i} className="flex items-center gap-2 flex-1">
              <div
                className={cn(
                  "w-6 h-6 rounded-full text-xs font-mono font-semibold flex items-center justify-center shrink-0 transition-colors",
                  done ? "bg-white text-black" :
                  active ? "bg-neutral-800 text-white border border-neutral-600" :
                  "bg-neutral-950 text-neutral-600 border border-neutral-900"
                )}
              >
                {done ? "✓" : num}
              </div>
              <span className={cn(
                "text-xs font-medium hidden sm:block truncate transition-colors",
                active ? "text-white" : done ? "text-neutral-300" : "text-neutral-600"
              )}>
                {s.label}
              </span>
              {i < STEPS.length - 1 && (
                <div className={cn(
                  "flex-1 h-px mx-1 transition-colors",
                  done ? "bg-neutral-500" : "bg-neutral-900"
                )} />
              )}
            </div>
          );
        })}
      </div>

      {/* Step content */}
      <div key={step}>
        {step === 1 && <Step1 state={state} update={update} onNext={() => setStep(2)} />}
        {step === 2 && <Step2 state={state} update={update} onNext={() => setStep(3)} onBack={() => setStep(1)} />}
        {step === 3 && <Step3 state={state} onNext={() => setStep(4)} onBack={() => setStep(2)} />}
        {step === 4 && <Step4 state={state} update={update} onNext={() => setStep(5)} onBack={() => setStep(3)} />}
        {step === 5 && (
          <Step5
            state={state}
            update={update}
            onBack={() => setStep(4)}
            onSubmit={handleSubmit}
            submitting={submitting}
          />
        )}
      </div>
      {submitError && (
        <div className="p-3 rounded-lg border border-rose-900 bg-rose-950/30 text-xs text-rose-300">
          {submitError}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────
// Step 1: Study Type
// ─────────────────────────────────────────
function Step1({ state, update, onNext }: {
  state: WizardState;
  update: (u: Partial<WizardState>) => void;
  onNext: () => void;
}) {
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">第 1 步 / 共 5 步</div>
        <h2 className="font-display text-xl font-semibold text-white tracking-tight">选择您的商业出海场景</h2>
        <p className="text-xs text-neutral-400 font-light mt-1">选择目标国家后，系统会加载对应的官方宏观人口、收入、地区与币种配置。</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {([
          { code: "TH", label: "泰国", detail: "NSO · THB · 77 府" },
          { code: "MY", label: "马来西亚", detail: "DOSM · MYR · 16 州/联邦直辖区" },
        ] as const).map(market => (
          <button
            type="button"
            key={market.code}
            onClick={() => update({ country_code: market.code })}
            className={cn(
              "card-lazzor p-4 text-left transition-colors",
              state.country_code === market.code ? "bg-neutral-900 border-neutral-500" : "hover:bg-[#171717]",
            )}
          >
            <div className="flex items-center justify-between">
              <strong className="text-sm text-white">{market.label}</strong>
              {state.country_code === market.code && <Check size={14} className="text-white" />}
            </div>
            <p className="text-[10px] text-neutral-500 mt-1">{market.detail}</p>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {Object.entries(STUDY_TYPE_META).map(([key, meta]) => {
          const active = state.study_type === key;
          return (
            <button
              key={key}
              onClick={() => update({ study_type: key as StudyType })}
              className={cn(
                "card-lazzor p-5 text-left transition-colors relative group",
                active ? "bg-neutral-900 border-neutral-600" : "hover:bg-[#171717]"
              )}
            >
              <div className="flex items-start gap-4">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center text-xl shrink-0"
                  style={{ background: `${meta.color}18` }}
                >
                  {meta.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className={cn("text-xs font-semibold tracking-tight", active ? "text-white" : "text-neutral-200")}>
                      {meta.label}
                    </span>
                    {active && <Check size={14} className="text-white" />}
                  </div>
                  <p className="text-[11px] text-neutral-400 font-light mt-1 line-clamp-2 leading-relaxed">{meta.desc}</p>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <div className="flex justify-end pt-4">
        <button
          onClick={onNext}
          disabled={!state.study_type}
          className={cn("btn-lazzor-primary", !state.study_type && "opacity-40 cursor-not-allowed")}
        >
          下一步 <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────
// Step 2: Input Data
// ─────────────────────────────────────────
function Step2({ state, update, onNext, onBack }: {
  state: WizardState;
  update: (u: Partial<WizardState>) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  const meta = state.study_type ? STUDY_TYPE_META[state.study_type] : null;
  const isProduct = state.study_type === "PRODUCT_VALIDATION";
  const isPricing = state.study_type === "PRICING_STUDY";
  const isCreative = state.study_type === "CREATIVE_TEST";
  const isOffline = Boolean(state.study_type && ["VENUE_STUDY", "SITE_COMPARISON", "OPERATING_SCENARIO"].includes(state.study_type));
  const siteCount = state.location_text.split(/[;\n、]+/).map(value => value.trim()).filter(Boolean).length;
  const market = state.country_code === "MY"
    ? { name: "马来西亚", currency: "MYR", symbol: "RM", priceExample: "99" }
    : { name: "泰国", currency: "THB", symbol: "฿", priceExample: "990" };

  const addListItem = (field: "selling_points" | "competitors") => {
    update({ [field]: [...state[field], ""] });
  };

  const updateListItem = (field: "selling_points" | "competitors", idx: number, val: string) => {
    const arr = [...state[field]];
    arr[idx] = val;
    update({ [field]: arr });
  };

  const removeListItem = (field: "selling_points" | "competitors", idx: number) => {
    const arr = state[field].filter((_, i) => i !== idx);
    update({ [field]: arr.length ? arr : [""] });
  };

  const canProceed = state.name.trim().length > 0
    && state.product_name.trim().length > 0
    && (isOffline
      ? state.location_text.trim().length > 0
        && Number(state.average_check) > 0
        && (state.study_type !== "SITE_COMPARISON" || siteCount >= 2)
      : isCreative
        ? true
        : Number(state.price) > 0);

  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">第 2 步 / 共 5 步</div>
        <h2 className="font-display text-xl font-semibold text-white tracking-tight">填写研究资料</h2>
        <p className="text-xs text-neutral-400 font-light mt-1">
          {meta ? `${meta.icon} ${meta.label} — ` : ""}
          输入越完整，模拟结果越有参考价值
        </p>
      </div>

      <div className="space-y-4">
        <Input
          label="项目名称"
          required
          placeholder={`例：${market.name}宠物饮水机上市验证`}
          value={state.name}
          onChange={e => update({ name: e.target.value })}
        />

        {/* Public research sources. These pages are processed only by the
            bounded, robots-aware public-evidence collector in Professional. */}
        <div className="space-y-1.5">
          <label className="block text-xs font-medium text-neutral-400 tracking-wide">产品 / 品牌官网（选填）</label>
          <div className="relative">
            <LinkIcon size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500" />
            <input
              className="input-lazzor pl-9"
              placeholder="https:// 产品官网或商品页"
              value={state.url}
              onChange={e => update({ url: e.target.value })}
            />
          </div>
        </div>

        <div className="space-y-2">
          <div>
            <label className="block text-xs font-medium text-neutral-400 tracking-wide">补充公开来源（选填）</label>
            <p className="mt-1 text-[11px] leading-5 text-neutral-500">
              可加入竞品商品页、公开评测或品牌页面。专业版会检查网站规则并抓取公开的价格、促销、评分、规格与消费者问题；登录页、验证码页和个人资料不会采集。
            </p>
          </div>
          {state.research_urls.map((value, index) => (
            <div className="flex gap-2" key={`research-url-${index}`}>
              <div className="relative flex-1">
                <LinkIcon size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500" />
                <input
                  className="input-lazzor pl-9"
                  placeholder="https:// 公开商品页、测评或竞品页"
                  value={value}
                  onChange={event => {
                    const researchUrls = [...state.research_urls];
                    researchUrls[index] = event.target.value;
                    update({ research_urls: researchUrls });
                  }}
                />
              </div>
              {state.research_urls.length > 1 && (
                <button
                  type="button"
                  aria-label="删除来源"
                  className="rounded-lg border border-neutral-800 px-3 text-neutral-500 transition hover:border-neutral-600 hover:text-white"
                  onClick={() => update({ research_urls: state.research_urls.filter((_, itemIndex) => itemIndex !== index) })}
                >
                  <X size={15} />
                </button>
              )}
            </div>
          ))}
          {state.research_urls.length < 5 && (
            <button
              type="button"
              className="inline-flex items-center gap-1.5 text-xs text-amber-300 transition hover:text-amber-200"
              onClick={() => update({ research_urls: [...state.research_urls, ""] })}
            >
              <Plus size={14} /> 添加公开来源
            </button>
          )}
        </div>

        {(isProduct || isPricing || isCreative) && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label={isCreative ? "推广的产品 / 品牌" : "产品名称"}
                required
                placeholder={isCreative ? "例：智能宠物饮水机" : "例：可折叠宠物推车"}
                value={state.product_name}
                onChange={e => update({ product_name: e.target.value })}
              />
              <div className="space-y-1.5">
                <label className="block text-xs font-medium text-neutral-400 tracking-wide">产品品类</label>
                <select className="input-lazzor" value={state.category} onChange={event => update({ category: event.target.value })}>
                  <option value="PET_WATER_FOUNTAIN">宠物智能饮水机{state.country_code === "TH" ? "（泰国有专属竞品面板）" : ""}</option>
                  <option value="BEAUTY_PERSONAL_CARE">美妆 / 个护</option>
                  <option value="FOOD_BEVERAGE">食品 / 饮料</option>
                  <option value="HOME_LIVING">家居 / 生活</option>
                  <option value="ELECTRONICS">数码 / 小家电</option>
                  <option value="PET_SUPPLIES">宠物用品</option>
                  <option value="GENERIC_CONSUMER_PRODUCT">其他消费品</option>
                </select>
              </div>
            </div>

            <div className="cmai-card p-4 space-y-3">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-xs font-medium text-white">产品图片（选填）</div>
                  <p className="text-[11px] text-neutral-500 mt-1">上传实物图、包装图或广告主图。系统会自动压缩并保存到本项目，不需要先上传到图床。</p>
                </div>
                {state.product_image_data_url ? (
                  <button type="button" onClick={() => update({ product_image_data_url: "" })} className="text-xs text-neutral-400 hover:text-white">移除图片</button>
                ) : null}
              </div>
              <div className="flex items-center gap-4">
                {state.product_image_data_url ? <img src={state.product_image_data_url} alt="产品预览" className="h-20 w-20 rounded-lg object-cover border border-neutral-800" /> : <div className="h-20 w-20 rounded-lg border border-dashed border-neutral-700 flex items-center justify-center text-neutral-500"><ImagePlus size={22} /></div>}
                <label className="btn-lazzor-ghost cursor-pointer">
                  <ImagePlus size={14} /> {state.product_image_data_url ? "更换图片" : "选择图片"}
                  <input
                    className="hidden"
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    onChange={async event => {
                      const file = event.target.files?.[0];
                      if (!file) return;
                      try {
                        update({ product_image_data_url: await compressImageForStudy(file) });
                      } catch (error) {
                        window.alert(error instanceof Error ? error.message : "图片处理失败，请重试。");
                      }
                    }}
                  />
                </label>
              </div>
            </div>

            {!isCreative && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <Input label={`${isPricing ? "当前测试价格" : "计划售价"}（${market.currency}）`} required type="number" placeholder={`例：${market.priceExample}`} value={state.price} onChange={e => update({ price: e.target.value })} />
                {isPricing && <Input label="市场常见价 / 竞品中位价（选填）" type="number" placeholder="例：1,190" value={state.reference_price} onChange={e => update({ reference_price: e.target.value })} />}
                {isPricing && <Input label="单件变动成本（选填）" type="number" placeholder="例：430" value={state.variable_cost} onChange={e => update({ variable_cost: e.target.value })} />}
              </div>
            )}
          </>
        )}

        {isCreative && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="block text-xs font-medium text-neutral-400 tracking-wide">要测试的素材形式</label>
                <select className="input-lazzor" value={state.creative_format} onChange={e => update({ creative_format: e.target.value })}>
                  <option value="IMAGE">广告图片</option>
                  <option value="COPY">广告文案</option>
                  <option value="VIDEO_SCRIPT">短视频脚本</option>
                  <option value="LANDING_PAGE">落地页</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="block text-xs font-medium text-neutral-400 tracking-wide">投放渠道</label>
                <select className="input-lazzor" value={state.channel} onChange={e => update({ channel: e.target.value })}>
                  <option value="META">Facebook / Instagram</option>
                  <option value="TIKTOK">TikTok</option>
                  <option value="LINE">LINE</option>
                  <option value="MARKETPLACE">Shopee / Lazada</option>
                </select>
              </div>
            </div>
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-neutral-400 tracking-wide">广告文案 / 视频脚本 / 主要信息（选填）</label>
              <textarea className="input-lazzor min-h-28 resize-y" placeholder="粘贴广告标题、正文、视频脚本或希望消费者看完后记住的信息。图片素材可直接在上方上传。" value={state.creative_content} onChange={e => update({ creative_content: e.target.value, description: e.target.value })} />
            </div>
          </>
        )}

        {state.template_key === "ECOMMERCE" && (
          <div className="cmai-card p-5 space-y-4">
            <div>
              <span className="eyebrow text-blue-300">{market.name}电商交易条件</span>
              <h3 className="text-sm font-semibold text-white mt-1">电商履约与平台信任</h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label={`预计运费（${market.currency}）`}
                type="number"
                value={state.shipping_fee}
                onChange={e => update({ shipping_fee: e.target.value })}
              />
              <Input
                label="预计送达天数"
                type="number"
                value={state.delivery_days}
                onChange={e => update({ delivery_days: e.target.value })}
              />
            </div>
            <div className="flex flex-wrap gap-5 text-xs text-neutral-300">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={state.cod_available} onChange={e => update({ cod_available: e.target.checked })} />
                支持货到付款（COD）
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={state.official_store} onChange={e => update({ official_store: e.target.checked })} />
                官方店 / Mall 标记
              </label>
            </div>
            <p className="text-[10px] text-neutral-500">默认比较 Shopee、Lazada 与 TikTok Shop；公开页面数据只作为报价和商品声明证据，不冒充成交量。</p>
          </div>
        )}

        {isOffline && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="门店 / 项目名称"
                required
                placeholder="例：Nimman 新概念咖啡馆"
                value={state.product_name}
                onChange={e => update({ product_name: e.target.value })}
              />
              <div className="space-y-1.5">
                <label className="block text-xs font-medium text-neutral-400 tracking-wide">业态</label>
                <select className="input-lazzor" value={state.venue_type} onChange={e => update({ venue_type: e.target.value })}>
                  <option value="RESTAURANT">餐厅</option>
                  <option value="CAFE">咖啡馆</option>
                  <option value="BAR">酒吧 / Pub</option>
                  <option value="RETAIL">零售门店</option>
                </select>
              </div>
            </div>
            <Input
              label={state.study_type === "SITE_COMPARISON" ? "候选地址或商圈（每行一个，至少两个）" : "门店地址或商圈"}
              required
              placeholder={state.study_type === "SITE_COMPARISON" ? "例：Thonglor, Bangkok\nEkkamai, Bangkok" : "例：Nimman Soi 9, Chiang Mai"}
              value={state.location_text}
              onChange={e => update({ location_text: e.target.value })}
            />
            {state.study_type === "SITE_COMPARISON" && (
              <p className="text-[11px] text-neutral-500 -mt-2">只需填写可搜索的地址或商圈名称。系统会在运行时自动解析坐标、路网和周边公开地点；无需填写经纬度。</p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Input
                label={`${state.study_type === "SITE_COMPARISON" ? "预计客单价" : "平均客单价"}（${market.currency}）`}
                type="number"
                required
                placeholder="例：350"
                value={state.average_check}
                onChange={e => update({ average_check: e.target.value, price: e.target.value })}
              />
              <Input
                label="容量 / 座位数"
                type="number"
                placeholder="例：60"
                value={state.capacity}
                onChange={e => update({ capacity: e.target.value })}
              />
              <Input
                label="营业时间"
                placeholder="例：10:00–22:00"
                value={state.opening_hours}
                onChange={e => update({ opening_hours: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-neutral-400 tracking-wide">
                既有门店数据（选填，用来提高准确度）
              </label>
              <textarea
                className="input-lazzor min-h-24 resize-y"
                placeholder={"多店校准：门店地址,日均客流\n小时校准：2026-07-01,10,35,60\n每行一条；没有数据可以留空"}
                value={state.venue_history_text}
                onChange={event => update({ venue_history_text: event.target.value })}
              />
              <p className="text-[10px] text-neutral-500">
                多店数据至少 4 个地址才能校准选址权重；小时客流至少覆盖 4 个时段并达到基本样本量。系统会明确标记为“客户数据校准”，不会和公开数据混在一起。
              </p>
            </div>
          </>
        )}

        {/* Selling points */}
        <div className="space-y-2">
          <label className="block text-xs font-medium text-neutral-400 tracking-wide">{isOffline ? "招牌 / 服务特色" : isCreative ? "希望消费者记住的重点" : "核心卖点"}</label>
          {state.selling_points.map((sp, i) => (
            <div key={i} className="flex gap-2">
              <input
                className="input-lazzor flex-1"
                placeholder={isOffline ? `特色 ${i + 1}，例：手冲咖啡 / 深夜营业` : `卖点 ${i + 1}`}
                value={sp}
                onChange={e => updateListItem("selling_points", i, e.target.value)}
              />
              {state.selling_points.length > 1 && (
                <button onClick={() => removeListItem("selling_points", i)} className="text-neutral-500 hover:text-neutral-300 p-2">
                  <X size={14} />
                </button>
              )}
            </div>
          ))}
          <button onClick={() => addListItem("selling_points")} className="text-xs text-neutral-300 hover:text-white flex items-center gap-1">
            <Plus size={13} /> 添加卖点
          </button>
        </div>

        {/* Competitors */}
        <div className="space-y-2">
          <label className="block text-xs font-medium text-neutral-400 tracking-wide">{isOffline ? "周边竞品或对标门店（选填）" : "竞品名称或公开网址（选填）"}</label>
          {state.competitors.map((c, i) => (
            <div key={i} className="flex gap-2">
              <input
                className="input-lazzor flex-1"
                placeholder={isOffline ? `竞品 ${i + 1}：名称、商场或地图链接` : `竞品 ${i + 1}：名称或商品网址`}
                value={c}
                onChange={e => updateListItem("competitors", i, e.target.value)}
              />
              {state.competitors.length > 1 && (
                <button onClick={() => removeListItem("competitors", i)} className="text-neutral-500 hover:text-neutral-300 p-2">
                  <X size={14} />
                </button>
              )}
            </div>
          ))}
          <button onClick={() => addListItem("competitors")} className="text-xs text-neutral-300 hover:text-white flex items-center gap-1">
            <Plus size={13} /> 添加竞品
          </button>
        </div>
      </div>

      <div className="flex justify-between pt-4">
        <button onClick={onBack} className="btn-lazzor-ghost">← 返回</button>
        <button
          onClick={onNext}
          disabled={!canProceed}
          className={cn("btn-lazzor-primary", !canProceed && "opacity-40 cursor-not-allowed")}
        >
          下一步 <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────
// Step 3: Assumption Confirmation
// ─────────────────────────────────────────
function Step3({ state, onNext, onBack }: {
  state: WizardState;
  onNext: () => void;
  onBack: () => void;
}) {
  const meta = state.study_type ? STUDY_TYPE_META[state.study_type] : null;
  const isOffline = Boolean(state.study_type && ["VENUE_STUDY", "SITE_COMPARISON", "OPERATING_SCENARIO"].includes(state.study_type));
  const isCreative = state.study_type === "CREATIVE_TEST";
  const market = state.country_code === "MY"
    ? { name: "马来西亚", currency: "MYR", symbol: "RM", areas: "16 个州/联邦直辖区", source: "DOSM" }
    : { name: "泰国", currency: "THB", symbol: "฿", areas: "77 府", source: "NSO" };

  const facts = [
    state.product_name && { label: isOffline ? "门店 / 项目" : isCreative ? "推广产品 / 品牌" : "产品名称", value: state.product_name },
    (isOffline ? state.average_check : state.price) && {
      label: isOffline ? "平均客单价" : "售价",
      value: `${market.symbol}${isOffline ? state.average_check : state.price}（${market.currency}）`,
    },
    isOffline
      ? { label: "位置与业态", value: `${state.location_text} · ${state.venue_type}` }
      : { label: "产品品类", value: state.category === "PET_WATER_FOUNTAIN" ? "宠物智能饮水机" : "其他消费品" },
  ].filter(Boolean) as { label: string; value: string }[];

  const isPetWater = state.category === "PET_WATER_FOUNTAIN";
  const price = Number(state.price);
  const pricePosition = price < 1_200 ? "低于公开面板中位区间" : price > 2_500 ? "高于公开面板中位区间" : "位于公开面板主要区间";

  const inferences = [
    { label: "模拟市场", value: `${market.name}全国 ${market.areas}人口权重`, grade: "B" },
    { label: "人口与收入", value: `${market.source} 官方聚合统计校准`, grade: "B" },
    {
      label: isOffline ? "地理与客流参照" : isCreative ? "广告效果参照" : "价格参照",
      value: isOffline
        ? `运行时解析${market.name}地址、周边营业地点和步行路网；无历史数据时小时客流仍为先验`
        : isCreative
          ? "当前使用结构化反应先验，尚未接入真实曝光与点击"
          : isPetWater && state.country_code === "TH" ? `${pricePosition}（公开样本 ฿435–฿3,290）` : "尚无该国家该品类实证价格面板",
      grade: isOffline || (isPetWater && state.country_code === "TH") ? "B" : "D",
    },
    {
      label: "竞品选择集",
      value: isPetWater && state.country_code === "TH" ? "15 个泰国公开零售报价，模拟时压缩为代表性选择集" : isOffline ? "用户输入周边竞品 + 不到店选项" : "用户输入竞品 + 不购买选项",
      grade: isPetWater && state.country_code === "TH" ? "B" : "D",
    },
  ];

  const defaults = [
    { label: "品牌认知与信任", value: "无客户历史数据，使用保守先验并纳入敏感性分析", grade: "D" },
    { label: "品类渗透与购买频率", value: isPetWater ? "宠物家庭资格率为工程先验，非官方实测" : "未校准，结果仅作方向性比较", grade: "D" },
    {
      label: "转化基准",
      value: isOffline
        ? state.venue_history_text.trim()
          ? "将使用输入的门店数据校准；结果仍需通过留店或新店试营业验证"
          : "无真实到店、订单或试营业数据，不宣称为可验证客流预测"
        : isCreative
          ? "无真实曝光、点击或 A/B 数据，不宣称为可验证广告转化率"
          : "无真实销售或 A/B 数据，不宣称为可验证销量预测",
      grade: "D",
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">第 3 步 / 共 5 步</div>
        <h2 className="font-display text-xl font-semibold text-white tracking-tight">确认研究假设</h2>
        <p className="text-xs text-neutral-400 font-light mt-1">请检查以下内容，平台将基于此运行模拟</p>
      </div>

      <Card>
        <div className="eyebrow mb-3">01. 用户已确认的事实</div>
        <div className="space-y-2 text-xs">
          <div className="flex justify-between py-1.5 border-b border-neutral-900">
            <span className="text-neutral-400">项目名称</span>
            <span className="text-white font-medium">{state.name}</span>
          </div>
          <div className="flex justify-between py-1.5 border-b border-neutral-900">
            <span className="text-neutral-400">研究类型</span>
            <span className="text-white font-medium">{meta?.label}</span>
          </div>
          {facts.map((f, i) => (
            <div key={i} className="flex justify-between py-1.5 border-b border-neutral-900 last:border-0">
              <span className="text-neutral-400">{f.label}</span>
              <span className="text-white font-medium">{f.value}</span>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <div className="eyebrow mb-3">02. 系统根据数据作出的推断</div>
        <div className="space-y-2 text-xs">
          {inferences.map((inf, i) => (
            <div key={i} className="flex justify-between items-center py-1.5 border-b border-neutral-900 last:border-0">
              <span className="text-neutral-400">{inf.label}</span>
              <div className="flex items-center gap-2">
                <span className="text-neutral-200">{inf.value}</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-neutral-900 text-neutral-400">{inf.grade}级</span>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <div className="eyebrow mb-3">03. 缺少真实数据时采用的默认假设</div>
        <div className="space-y-2 text-xs">
          {defaults.map((d, i) => (
            <div key={i} className="flex justify-between items-center py-1.5 border-b border-neutral-900 last:border-0">
              <span className="text-neutral-400">{d.label}</span>
              <div className="flex items-center gap-2">
                <span className="text-neutral-300 font-light">{d.value}</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-neutral-900 text-neutral-400">{d.grade}级</span>
              </div>
            </div>
          ))}
        </div>
        <p className="text-[11px] text-neutral-400 font-light mt-3 p-3 bg-black rounded-lg border border-neutral-900">
          * B 级表示来自公开统计或可追溯市场样本；D 级表示尚未实证校准的工程假设。报告会披露来源、
          版本和不确定性，不会把 D 级结果写成真实消费者的实测购买率。
        </p>
      </Card>

      <div className="flex justify-between pt-4">
        <button onClick={onBack} className="btn-lazzor-ghost">← 返回</button>
        <button onClick={onNext} className="btn-lazzor-primary">
          确认并继续 <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────
// Step 4: Business Questions
// ─────────────────────────────────────────
function Step4({ state, update, onNext, onBack }: {
  state: WizardState;
  update: (u: Partial<WizardState>) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  const questions = getQuestions(state.study_type);

  const toggle = (q: string) => {
    const current = state.business_questions;
    if (current.includes(q)) {
      update({ business_questions: current.filter(x => x !== q) });
    } else {
      update({ business_questions: [...current, q] });
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">第 4 步 / 共 5 步</div>
        <h2 className="font-display text-xl font-semibold text-white tracking-tight">选择重点商业问题</h2>
        <p className="text-xs text-neutral-400 font-light mt-1">报告将针对选中的核心商业问题重点解答</p>
      </div>

      <div className="space-y-2">
        {questions.map((q, i) => {
          const selected = state.business_questions.includes(q);
          return (
            <button
              key={i}
              onClick={() => toggle(q)}
              className={cn(
                "w-full card-lazzor p-4 text-left flex items-center gap-3 transition-colors",
                selected ? "bg-neutral-900 border-neutral-600" : "hover:bg-[#171717]"
              )}
            >
              <div className={cn(
                "w-4 h-4 rounded border flex items-center justify-center text-[10px] shrink-0 transition-colors",
                selected ? "bg-white text-black font-bold border-transparent" : "border-neutral-700"
              )}>
                {selected && "✓"}
              </div>
              <span className={cn("text-xs font-medium", selected ? "text-white" : "text-neutral-300")}>
                {q}
              </span>
            </button>
          );
        })}
      </div>

      <div className="flex justify-between pt-4">
        <button onClick={onBack} className="btn-lazzor-ghost">← 返回</button>
        <button onClick={onNext} className="btn-lazzor-primary">
          下一步 <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────
// Step 5: Scale Selection
// ─────────────────────────────────────────
function Step5({ state, update, onBack, onSubmit, submitting }: {
  state: WizardState;
  update: (u: Partial<WizardState>) => void;
  onBack: () => void;
  onSubmit: () => void;
  submitting: boolean;
}) {
  const selected = PLAN_META[state.plan_code];

  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">第 5 步 / 共 5 步</div>
        <h2 className="font-display text-xl font-semibold text-white tracking-tight">选择分析方式</h2>
        <p className="text-xs text-neutral-400 font-light mt-1">
          从免费检查、基础模拟、基础决策或深度决策中选择
        </p>
      </div>

      <div className="space-y-3">
        {(Object.entries(PLAN_META) as [PlanCode, typeof PLAN_META[PlanCode]][]).map(([code, plan]) => {
          const active = state.plan_code === code;
          return (
            <button
              key={code}
              onClick={() => update({ plan_code: code })}
              className={cn(
                "w-full card-lazzor p-5 text-left transition-colors relative",
                active ? "bg-neutral-900 border-neutral-600" : "hover:bg-[#171717]"
              )}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="font-semibold text-xs text-white">{plan.label}</span>
                  <span className="text-xs font-mono text-neutral-400">{plan.population.toLocaleString()} 人 AI 模拟消费人群</span>
                </div>
                {code === "PREVIEW" ? (
                  <span className="text-xs font-mono text-accent">免费</span>
                ) : (
                  <span className="text-xs text-neutral-400 font-mono">{plan.billing_label}</span>
                )}
              </div>
              <p className="text-[11px] text-neutral-400 font-light mt-1">{plan.desc}</p>
              <div className="flex items-center gap-3 mt-2 text-[10px] text-neutral-500 font-mono">
                <span>AI人群分析</span>
                <span>·</span>
                <span>{plan.scenarios} 个方案对比</span>
                <span>·</span>
                <span>
                  {code === "PROFESSIONAL"
                    ? "完整决策报告"
                    : code === "BASIC_DECISION"
                      ? "基础决策报告"
                      : code === "STANDARD"
                        ? "快速方案比较"
                        : "方向预览"}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      <Card className="bg-black">
        <div className="eyebrow mb-2">分析内容确认</div>
        <div className="space-y-1.5 text-xs font-light">
          <div className="flex justify-between"><span className="text-neutral-400">项目名称</span><span className="text-white">{state.name || "（未填写）"}</span></div>
          <div className="flex justify-between"><span className="text-neutral-400">研究类型</span><span className="text-white">{state.study_type ? STUDY_TYPE_META[state.study_type].label : "—"}</span></div>
          <div className="flex justify-between"><span className="text-neutral-400">分析方式</span><span className="text-white">{selected.label}</span></div>
          <div className="flex justify-between"><span className="text-neutral-400">AI人群规模</span><span className="text-white font-mono">{selected.population.toLocaleString()} 人</span></div>
          <div className="flex justify-between"><span className="text-neutral-400">本次消耗</span><span className="text-white font-mono">{selected.billing_label}</span></div>
        </div>
      </Card>

      <div className="flex justify-between pt-4">
        <button onClick={onBack} className="btn-lazzor-ghost">← 返回</button>
        <button onClick={onSubmit} disabled={submitting} className={cn("btn-lazzor-primary", submitting && "opacity-60 cursor-wait")}>
          {submitting ? "正在创建研究…" : "提交并立即运行 →"}
        </button>
      </div>
    </div>
  );
}
