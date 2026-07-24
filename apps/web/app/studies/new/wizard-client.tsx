"use client";

import { useState, useCallback, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Check, ChevronRight, Plus, X, Link as LinkIcon } from "lucide-react";
import { STUDY_TYPE_META, PLAN_META } from "@/lib/product-catalog";
import { getStoredToken } from "@/lib/auth-session";
import { Card, Input } from "@/components/ui";
import { cn } from "@/lib/utils";

type StudyType = keyof typeof STUDY_TYPE_META;
type PlanCode = keyof typeof PLAN_META;

interface WizardState {
  study_type: StudyType | null;
  name: string;
  description: string;
  product_name: string;
  category: string;
  price: string;
  selling_points: string[];
  competitors: string[];
  url: string;
  plan_code: PlanCode;
  business_questions: string[];
  venue_type: string;
  location_text: string;
  average_check: string;
  capacity: string;
  opening_hours: string;
  creative_format: string;
  channel: string;
}

const INIT_STATE: WizardState = {
  study_type: null,
  name: "",
  description: "",
  product_name: "",
  category: "GENERIC_CONSUMER_PRODUCT",
  price: "",
  selling_points: [""],
  competitors: [""],
  url: "",
  plan_code: "STANDARD",
  business_questions: [],
  venue_type: "RESTAURANT",
  location_text: "",
  average_check: "",
  capacity: "",
  opening_hours: "",
  creative_format: "IMAGE",
  channel: "META",
};

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

  const [step, setStep] = useState(initialType ? 2 : 1);
  const [state, setState] = useState<WizardState>({
    ...INIT_STATE,
    study_type: initialType,
    category: initialType && ["PRODUCT_VALIDATION", "PRICING_STUDY", "CREATIVE_TEST"].includes(initialType)
      ? initialCategory || INIT_STATE.category
      : INIT_STATE.category,
    venue_type: initialCategory || INIT_STATE.venue_type,
  });

  const update = useCallback((updates: Partial<WizardState>) => {
    setState(prev => ({ ...prev, ...updates }));
  }, []);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState<boolean | null>(null);
  const [returnPath, setReturnPath] = useState("/studies/new");

  useEffect(() => {
    setAuthReady(Boolean(getStoredToken()));
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
        plan_code: state.plan_code,
        product_name: state.product_name,
        category: state.category,
        price: state.price ? Number(state.price) : undefined,
        url: state.url,
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
        location: state.location_text
          ? { label: state.location_text }
          : undefined,
        candidate_locations: candidateLocations.map(label => ({ label })),
        scenarios: candidateLocations.map(label => ({
          name: label,
          price: Number(state.average_check),
        })),
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
    { label: "模拟规模" },
  ];

  if (authReady === null) {
    return <div className="p-8 text-xs text-neutral-400">正在检查工作区登录状态…</div>;
  }

  if (!authReady) {
    return (
      <div className="max-w-xl mx-auto p-8">
        <Card>
          <div className="eyebrow mb-2">Workspace required</div>
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
        <div className="eyebrow mb-1">Step 01</div>
        <h2 className="font-display text-xl font-semibold text-white tracking-tight">选择研究类型</h2>
        <p className="text-xs text-neutral-400 font-light mt-1">根据您的商业分析目标选择匹配的研究类型</p>
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
  const isProduct = !state.study_type || ["PRODUCT_VALIDATION", "PRICING_STUDY"].includes(state.study_type);
  const isCreative = state.study_type === "CREATIVE_TEST";
  const isOffline = Boolean(state.study_type && ["VENUE_STUDY", "SITE_COMPARISON", "OPERATING_SCENARIO"].includes(state.study_type));
  const siteCount = state.location_text.split(/[;\n、]+/).map(value => value.trim()).filter(Boolean).length;

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
    && (
      isOffline
        ? state.location_text.trim().length > 0
          && Number(state.average_check) > 0
          && (state.study_type !== "SITE_COMPARISON" || siteCount >= 2)
        : Number(state.price) > 0
    );

  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Step 02</div>
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
          placeholder="例：泰国宠物饮水机上市验证"
          value={state.name}
          onChange={e => update({ name: e.target.value })}
        />

        {/* URL input */}
        <div className="space-y-1.5">
          <label className="block text-xs font-medium text-neutral-400 tracking-wide">参考网址（选填）</label>
          <div className="relative">
            <LinkIcon size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500" />
            <input
              className="input-lazzor pl-9"
              placeholder="https:// 官网或产品页；将作为研究资料保存"
              value={state.url}
              onChange={e => update({ url: e.target.value })}
            />
          </div>
        </div>

        {/* Product info */}
        {(isProduct || isCreative) && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Input
              label={isCreative ? "推广产品 / 品牌" : "产品名称"}
              placeholder={isCreative ? "例：新款智能饮水机" : "例：BKK宠物零食"}
              value={state.product_name}
              onChange={e => update({ product_name: e.target.value })}
            />
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-neutral-400 tracking-wide">
                产品品类
              </label>
              <select
                className="input-lazzor"
                value={state.category}
                onChange={event => update({ category: event.target.value })}
              >
                <option value="PET_WATER_FOUNTAIN">
                  宠物智能饮水机（已连接竞品面板）
                </option>
                <option value="GENERIC_CONSUMER_PRODUCT">
                  其他消费品（通用品类先验）
                </option>
              </select>
            </div>
            <Input
              label={isCreative ? "产品售价 (THB)" : "售价 (THB)"}
              type="number"
              placeholder="例：299"
              value={state.price}
              onChange={e => update({ price: e.target.value })}
            />
          </div>
        )}

        {isCreative && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-neutral-400 tracking-wide">素材形式</label>
              <select className="input-lazzor" value={state.creative_format} onChange={e => update({ creative_format: e.target.value })}>
                <option value="IMAGE">广告图片</option>
                <option value="COPY">广告文案</option>
                <option value="VIDEO_SCRIPT">短视频脚本</option>
                <option value="LANDING_PAGE">落地页</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-neutral-400 tracking-wide">主要渠道</label>
              <select className="input-lazzor" value={state.channel} onChange={e => update({ channel: e.target.value })}>
                <option value="META">Facebook / Instagram</option>
                <option value="TIKTOK">TikTok</option>
                <option value="LINE">LINE</option>
                <option value="MARKETPLACE">Shopee / Lazada</option>
              </select>
            </div>
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
              label={state.study_type === "SITE_COMPARISON" ? "候选区域 / 点位（用分号或换行分隔）" : "城市、商圈或具体位置"}
              required
              placeholder="例：Chiang Mai, Nimman Soi 9"
              value={state.location_text}
              onChange={e => update({ location_text: e.target.value })}
            />
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Input
                label="平均客单价 (THB)"
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
          </>
        )}

        {/* Selling points */}
        <div className="space-y-2">
          <label className="block text-xs font-medium text-neutral-400 tracking-wide">核心卖点</label>
          {state.selling_points.map((sp, i) => (
            <div key={i} className="flex gap-2">
              <input
                className="input-lazzor flex-1"
                placeholder={`卖点 ${i + 1}`}
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
          <label className="block text-xs font-medium text-neutral-400 tracking-wide">竞品（选填）</label>
          {state.competitors.map((c, i) => (
            <div key={i} className="flex gap-2">
              <input
                className="input-lazzor flex-1"
                placeholder={`竞品 ${i + 1}`}
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

  const facts = [
    state.product_name && { label: isOffline ? "门店 / 项目" : isCreative ? "推广产品 / 品牌" : "产品名称", value: state.product_name },
    (isOffline ? state.average_check : state.price) && {
      label: isOffline ? "平均客单价" : "售价",
      value: `THB ${isOffline ? state.average_check : state.price}`,
    },
    isOffline
      ? { label: "位置与业态", value: `${state.location_text} · ${state.venue_type}` }
      : { label: "产品品类", value: state.category === "PET_WATER_FOUNTAIN" ? "宠物智能饮水机" : "其他消费品" },
  ].filter(Boolean) as { label: string; value: string }[];

  const isPetWater = state.category === "PET_WATER_FOUNTAIN";
  const price = Number(state.price);
  const pricePosition = price < 1_200 ? "低于公开面板中位区间" : price > 2_500 ? "高于公开面板中位区间" : "位于公开面板主要区间";

  const inferences = [
    { label: "模拟市场", value: "泰国全国 77 府人口权重", grade: "B" },
    { label: "人口与收入", value: "NSO 官方聚合统计校准", grade: "B" },
    {
      label: isOffline ? "地理与客流参照" : isCreative ? "广告效果参照" : "价格参照",
      value: isOffline
        ? "当前使用区域与出行阻力先验，尚未接入实时客流"
        : isCreative
          ? "当前使用结构化反应先验，尚未接入真实曝光与点击"
          : isPetWater ? `${pricePosition}（公开样本 ฿435–฿3,290）` : "尚无该品类实证价格面板",
      grade: isPetWater ? "B" : "D",
    },
    {
      label: "竞品选择集",
      value: isPetWater ? "15 个泰国公开零售报价，模拟时压缩为代表性选择集" : isOffline ? "用户输入周边竞品 + 不到店选项" : "用户输入竞品 + 不购买选项",
      grade: isPetWater ? "B" : "D",
    },
  ];

  const defaults = [
    { label: "品牌认知与信任", value: "无客户历史数据，使用保守先验并纳入敏感性分析", grade: "D" },
    { label: "品类渗透与购买频率", value: isPetWater ? "宠物家庭资格率为工程先验，非官方实测" : "未校准，结果仅作方向性比较", grade: "D" },
    {
      label: "转化基准",
      value: isOffline
        ? "无真实到店、订单或试营业数据，不宣称为可验证客流预测"
        : isCreative
          ? "无真实曝光、点击或 A/B 数据，不宣称为可验证广告转化率"
          : "无真实销售或 A/B 数据，不宣称为可验证销量预测",
      grade: "D",
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Step 03</div>
        <h2 className="font-display text-xl font-semibold text-white tracking-tight">确认研究假设</h2>
        <p className="text-xs text-neutral-400 font-light mt-1">请检查以下内容，平台将基于此运行模拟</p>
      </div>

      <Card>
        <div className="eyebrow mb-3">01. 已识别事实 (Identified Facts)</div>
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
        <div className="eyebrow mb-3">02. 系统推断 (System Inferences)</div>
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
        <div className="eyebrow mb-3">03. 缺失假设 (Missing Defaults)</div>
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
          * B 级表示公开统计或可追溯市场样本；D 级表示工程先验。报告会披露来源、版本与不确定性，不把 D 级结果包装成实测购买率。
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
        <div className="eyebrow mb-1">Step 04</div>
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
        <div className="eyebrow mb-1">Step 05</div>
        <h2 className="font-display text-xl font-semibold text-white tracking-tight">选择模拟规模与配置</h2>
        <p className="text-xs text-neutral-400 font-light mt-1">控制合成人口数量、Monte Carlo 轮数与情景数量</p>
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
                  <span className="text-xs font-mono text-neutral-400">{plan.population.toLocaleString()} 人</span>
                </div>
                {plan.price_thb > 0 ? (
                  <span className="text-xs font-bold text-white">฿{plan.price_thb.toLocaleString()}</span>
                ) : code === "PREVIEW" ? (
                  <span className="text-xs font-mono text-accent">Free</span>
                ) : (
                  <span className="text-xs text-neutral-400 font-mono">{plan.credits} 积分</span>
                )}
              </div>
              <p className="text-[11px] text-neutral-400 font-light mt-1">{plan.desc}</p>
              <div className="flex items-center gap-3 mt-2 text-[10px] text-neutral-500 font-mono">
                <span>Monte Carlo {plan.mc_rounds} 轮</span>
                <span>·</span>
                <span>{plan.scenarios} 个情景</span>
                <span>·</span>
                <span>消耗 {plan.credits} 积分</span>
              </div>
            </button>
          );
        })}
      </div>

      <Card className="bg-black">
        <div className="eyebrow mb-2">Order Summary</div>
        <div className="space-y-1.5 text-xs font-light">
          <div className="flex justify-between"><span className="text-neutral-400">项目名称</span><span className="text-white">{state.name || "（未填写）"}</span></div>
          <div className="flex justify-between"><span className="text-neutral-400">研究类型</span><span className="text-white">{state.study_type ? STUDY_TYPE_META[state.study_type].label : "—"}</span></div>
          <div className="flex justify-between"><span className="text-neutral-400">选择规模</span><span className="text-white font-mono">{selected.label} ({selected.population.toLocaleString()}人)</span></div>
          <div className="flex justify-between"><span className="text-neutral-400">消耗积分</span><span className="text-white font-mono">{selected.credits}</span></div>
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
