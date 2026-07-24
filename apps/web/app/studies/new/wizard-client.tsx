"use client";

import { useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Check, ChevronRight, Upload, Plus, X, MapPin, Link as LinkIcon } from "lucide-react";
import { STUDY_TYPE_META, PLAN_META } from "@/lib/mock-data";
import { Card, Input } from "@/components/ui";
import { cn } from "@/lib/utils";

type StudyType = keyof typeof STUDY_TYPE_META;
type PlanCode = keyof typeof PLAN_META;

interface WizardState {
  study_type: StudyType | null;
  name: string;
  description: string;
  product_name: string;
  price: string;
  selling_points: string[];
  competitors: string[];
  url: string;
  location_address: string;
  operating_hours_open: string;
  operating_hours_close: string;
  capacity: string;
  average_check: string;
  plan_code: PlanCode;
  business_questions: string[];
}

const INIT_STATE: WizardState = {
  study_type: null,
  name: "",
  description: "",
  product_name: "",
  price: "",
  selling_points: [""],
  competitors: [""],
  url: "",
  location_address: "",
  operating_hours_open: "09:00",
  operating_hours_close: "22:00",
  capacity: "",
  average_check: "",
  plan_code: "PROFESSIONAL",
  business_questions: [],
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
  RESTAURANT: [
    "哪个时段客流最高？",
    "最优营业时间是什么？",
    "适合家庭还是商务？",
    "外卖占比会有多高？",
    "容量设置是否合理？",
  ],
  CAFE: [
    "目标客群是哪些人？",
    "预计日均客流？",
    "高峰时段容量够吗？",
    "远程工作用户占比？",
    "复购率预期如何？",
  ],
  BAR: [
    "最佳营业时间区间？",
    "Happy Hour 效果如何？",
    "游客占比多少？",
    "活动对客流有多大提升？",
    "高峰时段容量是否充足？",
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
  const initialType = params.get("type") as StudyType | null;

  const [step, setStep] = useState(initialType ? 2 : 1);
  const [state, setState] = useState<WizardState>({
    ...INIT_STATE,
    study_type: initialType,
  });

  const update = useCallback((updates: Partial<WizardState>) => {
    setState(prev => ({ ...prev, ...updates }));
  }, []);

  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      // 1. Call real FastAPI backend to create study
      const { createStudyApi, confirmStudyApi } = await import("@/lib/api-client");
      const study = await createStudyApi({
        name: state.name || "未命名研究项目",
        study_type: state.study_type || "PRODUCT_VALIDATION",
        plan_code: state.plan_code,
        product_name: state.product_name,
        price: state.price ? parseFloat(state.price) : 299.0,
        url: state.url,
        description: state.description,
        selling_points: state.selling_points.filter(Boolean),
        competitors: state.competitors.filter(Boolean),
        business_questions: state.business_questions,
      });

      // 2. Confirm study facts
      await confirmStudyApi(study.id);

      // 3. Redirect to real-time run execution page
      router.push(`/studies/${study.id}/run?plan=${state.plan_code}`);
    } catch (err) {
      console.error("API submission error:", err);
      const mockId = `study_${Date.now()}`;
      router.push(`/studies/${mockId}/run?plan=${state.plan_code}`);
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
        {step === 5 && <Step5 state={state} update={update} onBack={() => setStep(4)} onSubmit={handleSubmit} />}
      </div>
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
  const isOnline = !state.study_type || ["PRODUCT_VALIDATION", "PRICING_STUDY", "CREATIVE_TEST"].includes(state.study_type);
  const isVenue = ["RESTAURANT", "CAFE", "BAR", "VENUE_STUDY", "SITE_COMPARISON", "OPERATING_SCENARIO", "RETAIL"].includes(state.study_type ?? "");

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

  const canProceed = state.name.trim().length > 0;

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
          placeholder="例：清迈中餐厅开业方案评估"
          value={state.name}
          onChange={e => update({ name: e.target.value })}
        />

        {/* Upload area */}
        <div className="space-y-1.5">
          <label className="block text-xs font-medium text-neutral-400 tracking-wide">上传文件</label>
          <div className="border border-dashed border-neutral-800 rounded-xl p-8 text-center hover:border-neutral-600 transition-colors cursor-pointer bg-neutral-950">
            <Upload size={20} className="text-neutral-500 mx-auto mb-2" />
            <p className="text-xs text-neutral-300 font-light">点击或拖放上传资料包</p>
            <p className="text-[11px] text-neutral-500 mt-1">支持：图片、PDF、Excel、菜单、广告素材</p>
          </div>
        </div>

        {/* URL input */}
        <div className="space-y-1.5">
          <label className="block text-xs font-medium text-neutral-400 tracking-wide">或输入网址</label>
          <div className="relative">
            <LinkIcon size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500" />
            <input
              className="input-lazzor pl-9"
              placeholder="https:// 官网、产品页或 Google Maps 链接"
              value={state.url}
              onChange={e => update({ url: e.target.value })}
            />
          </div>
        </div>

        {/* Product info */}
        {(isOnline || !state.study_type) && (
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="产品名称"
              placeholder="例：BKK宠物零食"
              value={state.product_name}
              onChange={e => update({ product_name: e.target.value })}
            />
            <Input
              label="售价 (THB)"
              type="number"
              placeholder="例：299"
              value={state.price}
              onChange={e => update({ price: e.target.value })}
            />
          </div>
        )}

        {/* Venue info */}
        {isVenue && (
          <>
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-neutral-400 tracking-wide">地址</label>
              <div className="relative">
                <MapPin size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500" />
                <input
                  className="input-lazzor pl-9"
                  placeholder="输入地址或 Google Maps 链接"
                  value={state.location_address}
                  onChange={e => update({ location_address: e.target.value })}
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <Input
                label="营业开始"
                type="time"
                value={state.operating_hours_open}
                onChange={e => update({ operating_hours_open: e.target.value })}
              />
              <Input
                label="营业结束"
                type="time"
                value={state.operating_hours_close}
                onChange={e => update({ operating_hours_close: e.target.value })}
              />
              <Input
                label="座位数"
                type="number"
                placeholder="例：50"
                value={state.capacity}
                onChange={e => update({ capacity: e.target.value })}
              />
            </div>
            <Input
              label="平均客单价 (THB)"
              type="number"
              placeholder="例：350"
              value={state.average_check}
              onChange={e => update({ average_check: e.target.value })}
            />
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

  const facts = [
    state.product_name && { label: "产品名称", value: state.product_name },
    state.price && { label: "售价", value: `THB ${state.price}` },
    state.location_address && { label: "地址", value: state.location_address },
    state.capacity && { label: "容量", value: `${state.capacity} 座` },
    state.average_check && { label: "客单价", value: `THB ${state.average_check}` },
  ].filter(Boolean) as { label: string; value: string }[];

  const inferences = [
    { label: "目标市场", value: "泰国曼谷/清迈城市消费者", grade: "B" },
    { label: "价格定位", value: state.price && Number(state.price) > 500 ? "中高端" : "大众市场", grade: "B" },
    { label: "目标人群", value: "25-40岁有收入成年人", grade: "C" },
  ];

  const defaults = [
    { label: "广告曝光预算", value: "未提供，使用行业中位数估算", grade: "D" },
    { label: "竞争强度", value: "未提供，使用地区平均水平", grade: "D" },
    { label: "复购周期", value: "未提供，使用类别默认值", grade: "D" },
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
          * D 级假设基于专家与历史数据估估算。模拟报告中将暴露对应的敏感性与不确定性范围。
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
function Step5({ state, update, onBack, onSubmit }: {
  state: WizardState;
  update: (u: Partial<WizardState>) => void;
  onBack: () => void;
  onSubmit: () => void;
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
                  <span className="text-xs text-neutral-500 font-mono">Custom</span>
                )}
              </div>
              <p className="text-[11px] text-neutral-400 font-light mt-1">{plan.desc}</p>
              <div className="flex items-center gap-3 mt-2 text-[10px] text-neutral-500 font-mono">
                <span>Monte Carlo {plan.mc_rounds} 轮</span>
                <span>·</span>
                <span>{plan.scenarios} 个情景</span>
                <span>·</span>
                <span>消耗 {plan.credits} 额度</span>
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
          <div className="flex justify-between"><span className="text-neutral-400">消耗额度</span><span className="text-white font-mono">{selected.credits} 次</span></div>
        </div>
      </Card>

      <div className="flex justify-between pt-4">
        <button onClick={onBack} className="btn-lazzor-ghost">← 返回</button>
        <button onClick={onSubmit} className="btn-lazzor-primary">
          提交并立即运行 →
        </button>
      </div>
    </div>
  );
}
