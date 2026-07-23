"use client";

import { useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Check, ChevronRight, Upload, Plus, X, MapPin, Link as LinkIcon } from "lucide-react";
import { STUDY_TYPE_META, PLAN_META } from "@/lib/mock-data";
import { Card, Input, ProgressBar } from "@/components/ui";
import { cn } from "@/lib/utils";

// ─── Types ───────────────────────────────
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

// ─────────────────────────────────────────
// Main Wizard
// ─────────────────────────────────────────
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

  const isOnlineType = (t: StudyType | null) =>
    !t || ["PRODUCT_VALIDATION", "PRICING_STUDY", "CREATIVE_TEST"].includes(t);

  const handleSubmit = () => {
    // In production: POST /v1/studies then redirect
    const mockId = `study_${Date.now()}`;
    router.push(`/studies/${mockId}/run`);
  };

  const STEPS = [
    { label: "选择类型" },
    { label: "填写资料" },
    { label: "确认假设" },
    { label: "选择问题" },
    { label: "选择规模" },
  ];

  return (
    <div className="max-w-4xl mx-auto p-6 animate-fade-in-up">
      {/* Step indicators */}
      <div className="flex items-center gap-2 mb-8">
        {STEPS.map((s, i) => {
          const num = i + 1;
          const done = step > num;
          const active = step === num;
          return (
            <div key={i} className="flex items-center gap-2 flex-1">
              <div className={cn(
                "flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold shrink-0 transition-smooth",
                done ? "bg-emerald-500/20 text-emerald-400" :
                active ? "bg-[var(--color-gold-glow)] text-gold border border-[var(--color-gold)]" :
                "bg-[var(--color-bg-elevated)] text-muted"
              )}>
                {done ? <Check size={13} /> : num}
              </div>
              <span className={cn(
                "text-xs hidden sm:block transition-smooth",
                active ? "text-primary font-medium" :
                done ? "text-emerald-400" : "text-muted"
              )}>
                {s.label}
              </span>
              {i < STEPS.length - 1 && (
                <div className={cn(
                  "flex-1 h-px mx-1",
                  done ? "bg-emerald-500/30" : "bg-[var(--color-border-subtle)]"
                )} />
              )}
            </div>
          );
        })}
      </div>

      {/* Step content */}
      <div className="animate-fade-in-up" key={step}>
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
// Step 1: Select Study Type
// ─────────────────────────────────────────
function Step1({ state, update, onNext }: {
  state: WizardState;
  update: (u: Partial<WizardState>) => void;
  onNext: () => void;
}) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-primary">选择研究类型</h2>
        <p className="text-sm text-secondary mt-1">根据您的商业目标选择最合适的研究类型</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 stagger-children">
        {Object.entries(STUDY_TYPE_META).map(([key, meta]) => {
          const active = state.study_type === key;
          return (
            <button
              key={key}
              onClick={() => update({ study_type: key as StudyType })}
              className={cn(
                "glass-card p-4 text-left transition-smooth",
                active
                  ? "border-[var(--color-gold)] bg-[var(--color-gold-glow)]"
                  : "hover:border-[var(--color-border)] hover:bg-[var(--color-bg-elevated)]"
              )}
            >
              <div className="flex items-start gap-3">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center text-xl shrink-0"
                  style={{ background: `${meta.color}20` }}
                >
                  {meta.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={cn("font-semibold text-sm", active ? "text-gold" : "text-primary")}>
                      {meta.label}
                    </span>
                    {active && <Check size={14} className="text-gold" />}
                  </div>
                  <p className="text-xs text-muted mt-1 line-clamp-2">{meta.desc}</p>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {meta.outputs.slice(0, 3).map(o => (
                      <span key={o} className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-bg-base)] text-muted">
                        {o}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <div className="flex justify-end">
        <button
          onClick={onNext}
          disabled={!state.study_type}
          className={cn("btn-primary", !state.study_type && "opacity-40 cursor-not-allowed")}
        >
          下一步 <ChevronRight size={16} />
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
        <h2 className="text-xl font-bold text-primary">填写研究资料</h2>
        <p className="text-sm text-secondary mt-1">
          {meta ? `${meta.icon} ${meta.label} — ` : ""}
          输入越完整，模拟结果越有参考价值
        </p>
      </div>

      <div className="space-y-4">
        {/* Project name */}
        <Input
          label="项目名称"
          required
          placeholder="例：清迈中餐厅开业方案评估"
          value={state.name}
          onChange={e => update({ name: e.target.value })}
        />

        {/* Upload area */}
        <div className="space-y-1.5">
          <label className="block text-sm font-medium text-secondary">上传文件</label>
          <div className="border-2 border-dashed border-[var(--color-border)] rounded-xl p-8 text-center hover:border-[var(--color-gold-dim)] transition-smooth cursor-pointer">
            <Upload size={24} className="text-muted mx-auto mb-2" />
            <p className="text-sm text-secondary">拖放文件或点击上传</p>
            <p className="text-xs text-muted mt-1">支持：图片、PDF、Excel、菜单、广告图、Logo</p>
          </div>
        </div>

        {/* URL input */}
        <div className="space-y-1.5">
          <label className="block text-sm font-medium text-secondary">或输入网址</label>
          <div className="relative">
            <LinkIcon size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              className="input-field pl-9"
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
              placeholder="例：BKK宠物零食系列"
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
              <label className="block text-sm font-medium text-secondary">地址</label>
              <div className="relative">
                <MapPin size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                <input
                  className="input-field pl-9"
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
          <label className="block text-sm font-medium text-secondary">核心卖点</label>
          {state.selling_points.map((sp, i) => (
            <div key={i} className="flex gap-2">
              <input
                className="input-field flex-1"
                placeholder={`卖点 ${i + 1}，例：泰国独家配方`}
                value={sp}
                onChange={e => updateListItem("selling_points", i, e.target.value)}
              />
              {state.selling_points.length > 1 && (
                <button onClick={() => removeListItem("selling_points", i)}
                  className="text-muted hover:text-red-400 transition-smooth p-2">
                  <X size={16} />
                </button>
              )}
            </div>
          ))}
          <button onClick={() => addListItem("selling_points")}
            className="text-xs text-gold hover:text-gold-light transition-smooth flex items-center gap-1">
            <Plus size={14} /> 添加卖点
          </button>
        </div>

        {/* Competitors */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-secondary">竞品（选填）</label>
          {state.competitors.map((c, i) => (
            <div key={i} className="flex gap-2">
              <input
                className="input-field flex-1"
                placeholder={`竞品 ${i + 1}`}
                value={c}
                onChange={e => updateListItem("competitors", i, e.target.value)}
              />
              {state.competitors.length > 1 && (
                <button onClick={() => removeListItem("competitors", i)}
                  className="text-muted hover:text-red-400 transition-smooth p-2">
                  <X size={16} />
                </button>
              )}
            </div>
          ))}
          <button onClick={() => addListItem("competitors")}
            className="text-xs text-gold hover:text-gold-light transition-smooth flex items-center gap-1">
            <Plus size={14} /> 添加竞品
          </button>
        </div>

        {/* Description */}
        <div className="space-y-1.5">
          <label className="block text-sm font-medium text-secondary">补充说明（选填）</label>
          <textarea
            className="input-field resize-none h-20"
            placeholder="其他需要系统了解的信息..."
            value={state.description}
            onChange={e => update({ description: e.target.value })}
          />
        </div>
      </div>

      <div className="flex justify-between">
        <button onClick={onBack} className="btn-ghost">← 返回</button>
        <button
          onClick={onNext}
          disabled={!canProceed}
          className={cn("btn-primary", !canProceed && "opacity-40 cursor-not-allowed")}
        >
          下一步 <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────
// Step 3: Confirmation
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
    { label: "目标市场", value: "泰国曼谷/清迈城市消费者", confidence: "B" },
    { label: "价格定位", value: state.price && Number(state.price) > 500 ? "中高端" : "大众市场", confidence: "B" },
    { label: "目标人群", value: "25-40岁有收入成年人", confidence: "C" },
  ];

  const defaults = [
    { label: "广告曝光预算", value: "未提供，使用行业中位数估算", grade: "D" },
    { label: "竞争强度", value: "未提供，使用地区平均水平", grade: "D" },
    { label: "复购周期", value: "未提供，使用类别默认值", grade: "D" },
    { label: "停车位", value: "未提供，假设有停车位", grade: "D" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-primary">确认研究参数</h2>
        <p className="text-sm text-secondary mt-1">请检查以下内容，系统将基于此运行模拟</p>
      </div>

      {/* Identified facts */}
      <ConfirmSection
        title="已识别事实"
        badge="来自您的输入，可修改"
        badgeColor="text-emerald-400 bg-emerald-500/10"
        dot="#22C55E"
      >
        {facts.length > 0 ? (
          <div className="grid grid-cols-2 gap-3">
            {facts.map((f, i) => (
              <div key={i} className="flex justify-between items-center py-2 border-b border-[var(--color-border-subtle)] last:border-0">
                <span className="text-xs text-muted">{f.label}</span>
                <span className="text-xs font-medium text-primary">{f.value}</span>
              </div>
            ))}
            <div className="flex justify-between items-center py-2 border-b border-[var(--color-border-subtle)]">
              <span className="text-xs text-muted">项目名称</span>
              <span className="text-xs font-medium text-primary">{state.name}</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-[var(--color-border-subtle)]">
              <span className="text-xs text-muted">研究类型</span>
              <span className="text-xs font-medium text-primary">{meta?.label}</span>
            </div>
          </div>
        ) : (
          <p className="text-xs text-muted">请返回填写更多资料以提高结果准确性</p>
        )}
      </ConfirmSection>

      {/* System inferences */}
      <ConfirmSection
        title="系统推断"
        badge="系统根据输入推断，请确认"
        badgeColor="text-amber-400 bg-amber-500/10"
        dot="#F59E0B"
      >
        <div className="space-y-2">
          {inferences.map((inf, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-[var(--color-border-subtle)] last:border-0">
              <span className="text-xs text-muted">{inf.label}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-primary">{inf.value}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400">
                  {inf.confidence}级
                </span>
              </div>
            </div>
          ))}
        </div>
      </ConfirmSection>

      {/* Missing defaults */}
      <ConfirmSection
        title="缺失假设（使用默认值）"
        badge="未提供，使用平台默认，可修改"
        badgeColor="text-blue-400 bg-blue-500/10"
        dot="#3B82F6"
      >
        <div className="space-y-2">
          {defaults.map((d, i) => (
            <div key={i} className="flex items-start justify-between py-2 border-b border-[var(--color-border-subtle)] last:border-0">
              <span className="text-xs text-muted">{d.label}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-secondary text-right max-w-48">{d.value}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 shrink-0">
                  {d.grade}级
                </span>
              </div>
            </div>
          ))}
        </div>
        <p className="text-xs text-muted mt-3 p-3 bg-[var(--color-bg-base)] rounded-lg">
          ⚠️ D级假设基于专家估算，结果报告中将明确标注不确定性范围。客户输入越完整，D级假设越少。
        </p>
      </ConfirmSection>

      <div className="flex justify-between">
        <button onClick={onBack} className="btn-ghost">← 返回</button>
        <button onClick={onNext} className="btn-primary">
          确认并继续 <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}

function ConfirmSection({
  title, badge, badgeColor, dot, children
}: {
  title: string;
  badge: string;
  badgeColor: string;
  dot: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <div className="flex items-center gap-3 mb-4">
        <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: dot, boxShadow: `0 0 6px ${dot}` }} />
        <h3 className="text-sm font-semibold text-primary">{title}</h3>
        <span className={cn("status-badge ml-auto text-[10px]", badgeColor)}>{badge}</span>
      </div>
      {children}
    </Card>
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
        <h2 className="text-xl font-bold text-primary">选择商业问题</h2>
        <p className="text-sm text-secondary mt-1">选择您最想得到答案的问题（可多选）</p>
      </div>

      <div className="space-y-2 stagger-children">
        {questions.map((q, i) => {
          const selected = state.business_questions.includes(q);
          return (
            <button
              key={i}
              onClick={() => toggle(q)}
              className={cn(
                "w-full glass-card p-4 text-left flex items-center gap-3 transition-smooth",
                selected ? "border-[var(--color-gold)] bg-[var(--color-gold-glow)]" : "hover:border-[var(--color-border)]"
              )}
            >
              <div className={cn(
                "w-5 h-5 rounded shrink-0 border flex items-center justify-center transition-smooth",
                selected ? "bg-[var(--color-gold)] border-[var(--color-gold)]" : "border-[var(--color-border)]"
              )}>
                {selected && <Check size={12} className="text-[#0A1628]" />}
              </div>
              <span className={cn("text-sm", selected ? "text-primary font-medium" : "text-secondary")}>
                {q}
              </span>
            </button>
          );
        })}
      </div>

      <p className="text-xs text-muted">
        已选 <span className="text-gold font-medium">{state.business_questions.length}</span> 个问题。
        报告将重点呈现这些问题的答案。
      </p>

      <div className="flex justify-between">
        <button onClick={onBack} className="btn-ghost">← 返回</button>
        <button onClick={onNext} className="btn-primary">
          下一步 <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────
// Step 5: Select Plan
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
        <h2 className="text-xl font-bold text-primary">选择模拟规模</h2>
        <p className="text-sm text-secondary mt-1">规模越大，结果越稳定，成本越高</p>
      </div>

      <div className="space-y-3 stagger-children">
        {(Object.entries(PLAN_META) as [PlanCode, typeof PLAN_META[PlanCode]][]).map(([code, plan]) => {
          const active = state.plan_code === code;
          return (
            <button
              key={code}
              onClick={() => update({ plan_code: code })}
              className={cn(
                "w-full glass-card p-4 text-left transition-smooth relative",
                active ? "border-[var(--color-gold)] bg-[var(--color-gold-glow)]" : "hover:border-[var(--color-border)]"
              )}
            >
              {(plan as any).popular && (
                <span className="absolute -top-2 right-4 text-[10px] font-bold px-2 py-0.5 rounded-full"
                  style={{ background: "linear-gradient(90deg,#D4A853,#B8902E)", color: "#0A1628" }}>
                  推荐
                </span>
              )}
              <div className="flex items-center gap-4">
                <div className="flex items-center justify-center w-5 h-5 rounded-full border shrink-0 transition-smooth"
                  style={{
                    borderColor: active ? plan.color : "var(--color-border)",
                    background: active ? `${plan.color}20` : "transparent",
                  }}>
                  {active && <span className="w-2.5 h-2.5 rounded-full" style={{ background: plan.color }} />}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <span className="font-semibold text-primary">{plan.label}</span>
                    <span className="text-sm" style={{ color: plan.color }}>
                      {plan.population.toLocaleString()} 人
                    </span>
                    {plan.price_thb > 0 ? (
                      <span className="ml-auto text-sm font-bold text-primary">
                        ฿{plan.price_thb.toLocaleString()}
                      </span>
                    ) : code === "PREVIEW" ? (
                      <span className="ml-auto text-sm font-bold text-emerald-400">免费</span>
                    ) : (
                      <span className="ml-auto text-sm text-muted">询价</span>
                    )}
                  </div>
                  <p className="text-xs text-muted mt-0.5">{plan.desc}</p>
                  <div className="flex gap-3 mt-1 text-xs text-muted">
                    <span>Monte Carlo {plan.mc_rounds} 轮</span>
                    <span>·</span>
                    <span>{plan.scenarios} 个情景</span>
                    <span>·</span>
                    <span>消耗 {plan.credits} 额度</span>
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Summary */}
      <Card className="bg-[var(--color-bg-base)]">
        <h3 className="text-sm font-semibold text-primary mb-3">提交摘要</h3>
        <div className="space-y-2 text-xs">
          <SummaryRow label="项目名称" value={state.name || "（未填写）"} />
          <SummaryRow label="研究类型" value={state.study_type ? STUDY_TYPE_META[state.study_type].label : "—"} />
          <SummaryRow label="模拟规模" value={`${selected.label} · ${selected.population.toLocaleString()} 人`} />
          <SummaryRow label="情景数量" value={`${selected.scenarios} 个`} />
          <SummaryRow label="Monte Carlo 轮数" value={`${selected.mc_rounds} 轮`} />
          <SummaryRow label="消耗额度" value={`${selected.credits} 次`} />
          {selected.price_thb > 0 && (
            <SummaryRow label="费用" value={`฿${selected.price_thb.toLocaleString()}`} />
          )}
        </div>
        <div className="divider my-3" />
        <p className="text-xs text-muted">
          预计运行时间：{
            state.plan_code === "PREVIEW" ? "1-3 分钟" :
            state.plan_code === "STANDARD" ? "5-15 分钟" :
            state.plan_code === "PROFESSIONAL" ? "15-30 分钟" :
            state.plan_code === "DEEP" ? "25-40 分钟" : "30-45 分钟"
          }。可关闭页面，完成后将通知您。
        </p>
      </Card>

      <div className="flex justify-between">
        <button onClick={onBack} className="btn-ghost">← 返回</button>
        <div className="flex gap-3">
          <button className="btn-secondary">保存草稿</button>
          <button onClick={onSubmit} className="btn-primary">
            提交运行 →
          </button>
        </div>
      </div>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted">{label}</span>
      <span className="text-secondary font-medium">{value}</span>
    </div>
  );
}
