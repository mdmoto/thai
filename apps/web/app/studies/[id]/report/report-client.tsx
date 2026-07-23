"use client";

import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  LineChart, Line, CartesianGrid,
  FunnelChart, Funnel, LabelList,
} from "recharts";
import { Info, ChevronDown, ChevronUp, AlertTriangle } from "lucide-react";
import { Card } from "@/components/ui";
import { cn, formatPercent } from "@/lib/utils";

// ── Mock report data ──────────────────────
const MOCK_REPORT = {
  study_name: "清迈 BKK 品牌宠物零食泰国市场测试",
  run_id: "run_20260720_001",
  world_model_version: "TH-WORLD-2026.07.1",
  simulation_model_version: "SIM-1.2.0",
  population_size: 30000,
  mc_rounds: 50,
  generated_at: "2026-07-20T11:30:00Z",
  executive: {
    recommendation: "✅ 方案值得推进，但需在定价和渠道上做调整",
    best_audience: "25-35岁曼谷/清迈城市女性，养宠物，月收入 3-6 万泰铢",
    main_barrier: "品牌知名度不足（72%未听说过），价格略高于主流竞品",
    best_scenario: "方案B：降价10% + Lazada 主推渠道",
    next_steps: [
      "优先在 Lazada 泰国开店，利用平台已有宠物品类流量",
      "将定价调整至 THB 249（当前 299），测试转化提升",
      "针对清迈宠物主社群做 KOL 合作，提高初始知名度",
    ],
    key_metrics: [
      { label: "购买意向率", value: 0.287, ci: [0.241, 0.334], unit: "%" },
      { label: "认知率", value: 0.43, ci: [0.38, 0.49], unit: "%" },
      { label: "价格接受度", value: 0.61, ci: [0.54, 0.68], unit: "%" },
      { label: "复购率（预测）", value: 0.52, ci: [0.44, 0.61], unit: "%" },
    ],
  },
  funnel: [
    { stage: "目标人口", label: "Eligible", value: 30000 },
    { stage: "曝光触达", label: "Exposed", value: 12900 },
    { stage: "引起注意", label: "Noticed", value: 7224 },
    { stage: "理解产品", label: "Understood", value: 5779 },
    { stage: "产生兴趣", label: "Interested", value: 3668 },
    { stage: "信任品牌", label: "Trusted", value: 2057 },
    { stage: "考虑购买", label: "Considered", value: 1131 },
    { stage: "完成购买", label: "Purchased", value: 860 },
  ],
  segments: [
    { name: "宠物专属主妇", size: 0.18, purchase_rate: 0.42, drivers: ["宠物健康", "方便购买"], barriers: ["价格敏感"] },
    { name: "都市白领宠物主", size: 0.24, purchase_rate: 0.38, drivers: ["品质感", "外观"], barriers: ["品牌陌生"] },
    { name: "年轻单身宠物主", size: 0.31, purchase_rate: 0.22, drivers: ["新奇", "社群分享"], barriers: ["价格", "品牌信任"] },
    { name: "家庭宠物用户", size: 0.14, purchase_rate: 0.19, drivers: ["安全", "口碑"], barriers: ["不活跃网购"] },
    { name: "低参与度宠物主", size: 0.13, purchase_rate: 0.06, drivers: [], barriers: ["无需求", "价格"] },
  ],
  scenarios: [
    { name: "基准方案 A\nTHB 299 / Lazada+Shopee", purchase_rate: 0.287, revenue_idx: 100, margin_idx: 100 },
    { name: "方案 B\nTHB 249 / Lazada 主推", purchase_rate: 0.341, revenue_idx: 97, margin_idx: 88 },
    { name: "方案 C\nTHB 339 / 高端渠道", purchase_rate: 0.198, revenue_idx: 96, margin_idx: 118 },
    { name: "方案 D\nTHB 299 / 全渠道+KOL", purchase_rate: 0.318, revenue_idx: 108, margin_idx: 102 },
  ],
  consumer_voices: [
    {
      persona: "25岁清迈女性，养猫，月收入3.5万铢",
      segment: "年轻单身宠物主",
      sentiment: "positive",
      quote: "包装很好看，但我没听说过这个牌子，会先去看看评论",
      reasoning: "对新品牌持观望态度，评论是关键决策因素",
    },
    {
      persona: "38岁曼谷男性，养狗，月收入7万铢",
      segment: "都市白领宠物主",
      sentiment: "neutral",
      quote: "价格比较贵，但如果成分真的好可以考虑，需要了解更多",
      reasoning: "价格敏感但品质导向，需要更多产品信息",
    },
    {
      persona: "32岁清迈女性，养狗，月收入4万铢",
      segment: "宠物专属主妇",
      sentiment: "positive",
      quote: "成分表看起来不错！会买来试试，如果狗狗喜欢就继续买",
      reasoning: "健康成分是主要驱动因素，试用意愿高",
    },
  ],
  radar_data: [
    { subject: "产品契合", A: 72, B: 68, fullMark: 100 },
    { subject: "价格接受", A: 58, B: 71, fullMark: 100 },
    { subject: "品牌信任", A: 42, B: 42, fullMark: 100 },
    { subject: "渠道适配", A: 65, B: 78, fullMark: 100 },
    { subject: "传播潜力", A: 69, B: 66, fullMark: 100 },
    { subject: "复购倾向", A: 53, B: 58, fullMark: 100 },
  ],
};

// ── Sections ─────────────────────────────
const SECTIONS = [
  "executive_summary", "market_response", "segments",
  "scenarios", "consumer_voices", "sensitivity", "methodology"
] as const;

const SECTION_LABELS: Record<typeof SECTIONS[number], string> = {
  executive_summary: "执行摘要",
  market_response: "市场反应",
  segments: "人群分析",
  scenarios: "情景对比",
  consumer_voices: "消费者声音",
  sensitivity: "敏感性",
  methodology: "方法附录",
};

export function ReportClient({ studyId }: { studyId: string }) {
  const [activeSection, setActiveSection] = useState<typeof SECTIONS[number]>("executive_summary");

  return (
    <div className="flex h-full">
      {/* Section nav */}
      <aside className="w-48 shrink-0 border-r border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)] py-4 sticky top-0 h-screen overflow-y-auto">
        <div className="px-3 mb-3">
          <span className="section-heading">报告章节</span>
        </div>
        <nav className="space-y-0.5 px-2">
          {SECTIONS.map(sec => (
            <button
              key={sec}
              onClick={() => setActiveSection(sec)}
              className={cn(
                "w-full text-left px-3 py-2 rounded-lg text-xs transition-smooth",
                activeSection === sec
                  ? "bg-[var(--color-gold-glow)] text-gold font-medium"
                  : "text-muted hover:text-secondary hover:bg-[var(--color-bg-elevated)]"
              )}
            >
              {SECTION_LABELS[sec]}
            </button>
          ))}
        </nav>

        {/* Report metadata */}
        <div className="mx-3 mt-6 p-3 rounded-lg bg-[var(--color-bg-base)] text-[10px] text-muted space-y-1.5">
          <div>Run ID</div>
          <div className="font-mono text-secondary">{MOCK_REPORT.run_id}</div>
          <div className="mt-2">World Model</div>
          <div className="font-mono text-secondary">{MOCK_REPORT.world_model_version}</div>
          <div className="mt-2">模拟规模</div>
          <div className="text-secondary">{MOCK_REPORT.population_size.toLocaleString()} 人</div>
          <div className="mt-2">MC 轮数</div>
          <div className="text-secondary">{MOCK_REPORT.mc_rounds} 轮</div>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 overflow-y-auto p-6 space-y-6 animate-fade-in">
        {/* Study header */}
        <div>
          <h1 className="text-xl font-bold text-primary">{MOCK_REPORT.study_name}</h1>
          <p className="text-sm text-muted mt-1">
            {MOCK_REPORT.population_size.toLocaleString()} 人合成市场 · {MOCK_REPORT.mc_rounds} 轮 Monte Carlo · 2026-07-20
          </p>
        </div>

        {activeSection === "executive_summary" && <ExecutiveSummarySection />}
        {activeSection === "market_response" && <MarketResponseSection />}
        {activeSection === "segments" && <SegmentsSection />}
        {activeSection === "scenarios" && <ScenariosSection />}
        {activeSection === "consumer_voices" && <ConsumerVoicesSection />}
        {activeSection === "sensitivity" && <SensitivitySection />}
        {activeSection === "methodology" && <MethodologySection />}
      </main>
    </div>
  );
}

// ── Section components ──────────────────
function ExecutiveSummarySection() {
  const { executive } = MOCK_REPORT;
  return (
    <div className="space-y-5 animate-fade-in-up">
      {/* Verdict card */}
      <Card className="border-emerald-500/30">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/20 flex items-center justify-center text-xl shrink-0">✅</div>
          <div>
            <h2 className="font-bold text-primary text-sm mb-1">总体判断</h2>
            <p className="text-sm text-secondary">{executive.recommendation}</p>
          </div>
        </div>
      </Card>

      {/* Key metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {executive.key_metrics.map((m, i) => (
          <Card key={i} className="text-center">
            <MetricBlock
              label={m.label}
              value={formatPercent(m.value)}
              ci={`${formatPercent(m.ci[0])} – ${formatPercent(m.ci[1])}`}
              runId={MOCK_REPORT.run_id}
            />
          </Card>
        ))}
      </div>

      {/* 3 key findings */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <FindingCard icon="👥" title="最佳人群" content={executive.best_audience} color="#D4A853" />
        <FindingCard icon="🚧" title="主要阻力" content={executive.main_barrier} color="#EF4444" />
        <FindingCard icon="🏆" title="最优方案" content={executive.best_scenario} color="#22C55E" />
      </div>

      {/* Next steps */}
      <Card>
        <h3 className="text-sm font-semibold text-primary mb-3">下一步行动建议</h3>
        <ol className="space-y-3">
          {executive.next_steps.map((step, i) => (
            <li key={i} className="flex items-start gap-3 text-sm text-secondary">
              <span className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
                style={{ background: "var(--color-gold-glow)", color: "var(--color-gold)" }}>
                {i + 1}
              </span>
              {step}
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}

function MarketResponseSection() {
  const { funnel } = MOCK_REPORT;
  const max = funnel[0].value;

  return (
    <div className="space-y-5 animate-fade-in-up">
      <h2 className="text-base font-bold text-primary">市场反应漏斗</h2>
      <Card>
        <div className="space-y-2">
          {funnel.map((f, i) => (
            <div key={i} className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-muted">{f.label} · {f.stage}</span>
                <span className="text-secondary font-medium">
                  {f.value.toLocaleString()} ({formatPercent(f.value / max)})
                </span>
              </div>
              <div className="h-6 rounded bg-[var(--color-bg-base)] overflow-hidden">
                <div
                  className="h-full rounded flex items-center px-2 transition-all duration-700"
                  style={{
                    width: `${(f.value / max) * 100}%`,
                    background: `linear-gradient(90deg, var(--color-gold-dim), var(--color-gold))`,
                    opacity: 0.6 + (i / funnel.length) * 0.4,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
        <TraceabilityNote runId={MOCK_REPORT.run_id} metric="market_funnel" />
      </Card>
    </div>
  );
}

function SegmentsSection() {
  return (
    <div className="space-y-5 animate-fade-in-up">
      <h2 className="text-base font-bold text-primary">人群分析</h2>
      <div className="space-y-3">
        {MOCK_REPORT.segments.map((seg, i) => (
          <Card key={i}>
            <div className="flex items-start gap-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-semibold text-sm text-primary">{seg.name}</span>
                  <span className="text-xs text-muted">占比 {formatPercent(seg.size)}</span>
                </div>
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xs text-muted">购买意向率</span>
                  <div className="flex-1 max-w-32 h-1.5 bg-[var(--color-bg-base)] rounded overflow-hidden">
                    <div className="h-full rounded" style={{
                      width: `${seg.purchase_rate * 100}%`,
                      background: seg.purchase_rate > 0.3 ? "#22C55E" : seg.purchase_rate > 0.15 ? "#D4A853" : "#EF4444"
                    }} />
                  </div>
                  <span className="text-xs font-bold" style={{
                    color: seg.purchase_rate > 0.3 ? "#22C55E" : seg.purchase_rate > 0.15 ? "#D4A853" : "#EF4444"
                  }}>
                    {formatPercent(seg.purchase_rate)}
                  </span>
                </div>
                {seg.drivers.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {seg.drivers.map(d => (
                      <span key={d} className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400">↑ {d}</span>
                    ))}
                    {seg.barriers.map(b => (
                      <span key={b} className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-400">↓ {b}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function ScenariosSection() {
  return (
    <div className="space-y-5 animate-fade-in-up">
      <h2 className="text-base font-bold text-primary">情景对比</h2>
      <Card>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={MOCK_REPORT.scenarios} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(30,58,95,0.5)" />
              <XAxis dataKey="name" tick={{ fill: "#8FA3C0", fontSize: 10 }} />
              <YAxis tick={{ fill: "#8FA3C0", fontSize: 10 }} />
              <Tooltip
                contentStyle={{ background: "#0F1F3A", border: "1px solid #1E3A5F", borderRadius: 8, color: "#E8EDF5" }}
              />
              <Bar dataKey="purchase_rate" name="购买率" fill="var(--color-gold)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="revenue_idx" name="收入指数" fill="#3B82F6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="margin_idx" name="毛利指数" fill="#22C55E" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-4 grid grid-cols-4 gap-3">
          {MOCK_REPORT.scenarios.map((s, i) => (
            <div key={i} className={cn("p-3 rounded-lg text-center", i === 1 ? "bg-[var(--color-gold-glow)] border border-[var(--color-gold-dim)]" : "bg-[var(--color-bg-base)]")}>
              <div className="text-xs text-muted mb-1 leading-tight">{s.name}</div>
              <div className="text-sm font-bold" style={{ color: i === 1 ? "var(--color-gold)" : "var(--color-text-primary)" }}>
                {formatPercent(s.purchase_rate)}
              </div>
              {i === 1 && <div className="text-[10px] text-gold mt-0.5">推荐</div>}
            </div>
          ))}
        </div>
        <TraceabilityNote runId={MOCK_REPORT.run_id} metric="scenario_comparison" />
      </Card>
    </div>
  );
}

function ConsumerVoicesSection() {
  return (
    <div className="space-y-5 animate-fade-in-up">
      <h2 className="text-base font-bold text-primary">消费者声音</h2>
      <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-start gap-2">
        <AlertTriangle size={14} className="text-amber-400 shrink-0 mt-0.5" />
        <p className="text-xs text-amber-300">
          以下内容由代表性合成消费者生成，用于解释群体行为，不是真人访谈记录。
        </p>
      </div>
      <div className="space-y-4">
        {MOCK_REPORT.consumer_voices.map((v, i) => (
          <Card key={i}>
            <div className="flex items-start gap-3">
              <div className={cn(
                "w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0",
                v.sentiment === "positive" ? "bg-emerald-500/20 text-emerald-400" :
                v.sentiment === "neutral" ? "bg-amber-500/20 text-amber-400" :
                "bg-red-500/20 text-red-400"
              )}>
                {v.sentiment === "positive" ? "😊" : v.sentiment === "neutral" ? "😐" : "😕"}
              </div>
              <div>
                <p className="text-xs text-muted mb-2">{v.persona} · <span className="text-secondary">{v.segment}</span></p>
                <blockquote className="text-sm text-primary italic border-l-2 border-[var(--color-gold-dim)] pl-3 mb-2">
                  &ldquo;{v.quote}&rdquo;
                </blockquote>
                <p className="text-xs text-muted">{v.reasoning}</p>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function SensitivitySection() {
  const params = [
    { name: "价格", impact: 0.72, direction: "降价10% → 购买率+18%" },
    { name: "品牌信任", impact: 0.68, direction: "信任+0.1 → 购买率+12%" },
    { name: "曝光度", impact: 0.55, direction: "曝光+20% → 考虑+15%" },
    { name: "评分", impact: 0.41, direction: "评分4.5→5.0 → 转化+8%" },
    { name: "竞争强度", impact: 0.38, direction: "竞品+1 → 购买率-6%" },
    { name: "距离", impact: 0.12, direction: "（线上商品，影响小）" },
  ];

  return (
    <div className="space-y-5 animate-fade-in-up">
      <h2 className="text-base font-bold text-primary">敏感性分析</h2>
      <Card>
        <p className="text-xs text-muted mb-4">以下展示各参数对购买率影响的相对强度（影响系数越高越重要）</p>
        <div className="space-y-3">
          {params.map((p, i) => (
            <div key={i} className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-secondary font-medium">{p.name}</span>
                <span className="text-muted">{p.direction}</span>
              </div>
              <div className="h-2 bg-[var(--color-bg-base)] rounded overflow-hidden">
                <div
                  className="h-full rounded transition-all"
                  style={{
                    width: `${p.impact * 100}%`,
                    background: p.impact > 0.6 ? "#EF4444" : p.impact > 0.4 ? "#F59E0B" : "#22C55E"
                  }}
                />
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 p-3 rounded-lg bg-[var(--color-bg-base)] text-xs text-muted">
          <strong className="text-secondary">稳健结论：</strong> 价格和品牌信任是主要驱动因素，在多数参数变化下方向一致。<br />
          <strong className="text-secondary mt-1 block">敏感结论：</strong> 具体转化率数字对品牌信任假设较敏感（D级假设，结果仅供参考）。
        </div>
      </Card>
    </div>
  );
}

function MethodologySection() {
  return (
    <div className="space-y-5 animate-fade-in-up">
      <h2 className="text-base font-bold text-primary">方法附录</h2>
      <Card>
        <div className="space-y-4 text-sm text-secondary">
          <MethodBlock title="合成人口" content="使用 TH-WORLD-2026.07.1 生成 30,000 名合成泰国消费者。人口覆盖曼谷、清迈等主要城市，包含游客和常住人口。变量之间相关，不独立均匀随机。" />
          <MethodBlock title="代表性 Agent" content="对人口分群后，每群选取 3-6 名代表消费者（centroid / high_affinity / skeptical）调用 Gemini 产生结构化反应（JSON Schema 约束输出）。" />
          <MethodBlock title="响应模型" content="Agent 结果拟合逻辑回归响应模型，具备单调性约束。价格上升不在其他条件不变时提高购买率。" />
          <MethodBlock title="Monte Carlo" content={`共运行 ${MOCK_REPORT.mc_rounds} 轮。每轮对参数分布采样，包含曝光、个体阈值、社交传播和竞争反应的随机性。结果报告均值、中位数和 P10/P90 区间。`} />
          <MethodBlock title="数据追溯" content={`每个指标均可追溯至本次 Run ID（${MOCK_REPORT.run_id}）、World Model 版本（${MOCK_REPORT.world_model_version}）和 Simulation Model（${MOCK_REPORT.simulation_model_version}）。`} />
          <MethodBlock title="局限说明" content="本结果基于合成人口和行为模型，不是真人调查。不保证实际销量、客流或投资回报。结果适合比较方案、发现风险和形成假设，不可直接作为财务预测依据。" />
        </div>
      </Card>
    </div>
  );
}

// ── Sub-components ────────────────────────
function MetricBlock({ label, value, ci, runId }: {
  label: string; value: string; ci: string; runId: string;
}) {
  const [showTrace, setShowTrace] = useState(false);
  return (
    <div>
      <div className="text-2xl font-bold text-gradient-gold">{value}</div>
      <div className="text-xs text-secondary mt-1">{label}</div>
      <div className="text-[10px] text-muted mt-0.5">区间 {ci}</div>
      <button
        onClick={() => setShowTrace(!showTrace)}
        className="text-[10px] text-gold mt-1 flex items-center gap-0.5 hover:text-gold-light"
      >
        追溯 {showTrace ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
      </button>
      {showTrace && (
        <div className="mt-1 p-2 rounded bg-[var(--color-bg-base)] text-[10px] text-muted font-mono">
          run_id: {runId}<br />
          model: {MOCK_REPORT.simulation_model_version}<br />
          rounds: {MOCK_REPORT.mc_rounds}<br />
          n: {MOCK_REPORT.population_size.toLocaleString()}
        </div>
      )}
    </div>
  );
}

function FindingCard({ icon, title, content, color }: {
  icon: string; title: string; content: string; color: string;
}) {
  return (
    <Card>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">{icon}</span>
        <span className="text-xs font-semibold" style={{ color }}>{title}</span>
      </div>
      <p className="text-xs text-secondary leading-relaxed">{content}</p>
    </Card>
  );
}

function TraceabilityNote({ runId, metric }: { runId: string; metric: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-4">
      <button
        onClick={() => setOpen(!open)}
        className="text-[10px] text-muted hover:text-secondary flex items-center gap-1"
      >
        <Info size={10} /> 数字追溯 {open ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
      </button>
      {open && (
        <div className="mt-2 p-2 rounded bg-[var(--color-bg-base)] text-[10px] font-mono text-muted space-y-0.5">
          <div>run_id: {runId}</div>
          <div>metric: {metric}</div>
          <div>world_model: {MOCK_REPORT.world_model_version}</div>
          <div>sim_model: {MOCK_REPORT.simulation_model_version}</div>
          <div>rounds: {MOCK_REPORT.mc_rounds}</div>
          <div>population: {MOCK_REPORT.population_size.toLocaleString()}</div>
        </div>
      )}
    </div>
  );
}

function MethodBlock({ title, content }: { title: string; content: string }) {
  return (
    <div>
      <h4 className="text-sm font-semibold text-primary mb-1">{title}</h4>
      <p className="text-xs text-secondary leading-relaxed">{content}</p>
      <div className="divider mt-3" />
    </div>
  );
}
