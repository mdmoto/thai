"use client";

import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { Info, ChevronDown, ChevronUp, AlertTriangle, ArrowUpRight, Download, Share2 } from "lucide-react";
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
    recommendation: "方案值得推进。降价10%并优先在 Lazada 平台主推可显著提升购买意向率与净收益。",
    best_audience: "25-35岁曼谷/清迈城市女性，养宠物，月收入 3-6 万泰铢",
    main_barrier: "品牌知名度不足（72%未听说过），价格略高于主流竞品",
    best_scenario: "方案B：售价 THB 249 + Lazada 平台主推",
    next_steps: [
      "优先在 Lazada 泰国开店，利用平台已有宠物品类流量",
      "将定价调整至 THB 249（当前 299），测试转化提升",
      "针对清迈宠物主社群做 KOL 合作，提高初始知名度",
    ],
    key_metrics: [
      { label: "购买意向率", value: 0.287, ci: [0.241, 0.334] },
      { label: "认知率", value: 0.43, ci: [0.38, 0.49] },
      { label: "价格接受度", value: 0.61, ci: [0.54, 0.68] },
      { label: "复购率（预测）", value: 0.52, ci: [0.44, 0.61] },
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
};

const SECTIONS = [
  "executive_summary", "market_response", "segments",
  "scenarios", "consumer_voices", "sensitivity", "methodology"
] as const;

const SECTION_LABELS: Record<typeof SECTIONS[number], string> = {
  executive_summary: "执行摘要",
  market_response: "市场反应漏斗",
  segments: "人群分析",
  scenarios: "情景对比",
  consumer_voices: "消费者声音",
  sensitivity: "敏感性分析",
  methodology: "方法附录",
};

export function ReportClient({ studyId }: { studyId: string }) {
  const [activeSection, setActiveSection] = useState<typeof SECTIONS[number]>("executive_summary");
  const [reportData, setReportData] = useState<typeof MOCK_REPORT>(MOCK_REPORT);

  useEffect(() => {
    if (studyId && studyId.startsWith("rpt_")) {
      (async () => {
        try {
          const { getReportApi } = await import("@/lib/api-client");
          const data = await getReportApi(studyId);
          if (data) {
            setReportData(prev => ({
              ...prev,
              ...data,
              study_name: data.study_name || prev.study_name,
            }));
          }
        } catch (e) {
          console.log("Using cached report data:", e);
        }
      })();
    }
  }, [studyId]);

  return (
    <div className="flex h-full">
      {/* Section Nav */}
      <aside className="w-52 shrink-0 border-r border-neutral-900 bg-black py-6 sticky top-0 h-screen overflow-y-auto">
        <div className="px-4 mb-4">
          <span className="eyebrow">Report Index</span>
        </div>
        <nav className="space-y-1 px-2">
          {SECTIONS.map(sec => (
            <button
              key={sec}
              onClick={() => setActiveSection(sec)}
              className={cn(
                "w-full text-left px-3 py-2 rounded-lg text-xs font-medium transition-colors",
                activeSection === sec
                  ? "bg-neutral-900 text-white font-semibold"
                  : "text-neutral-400 hover:text-white hover:bg-neutral-900/40"
              )}
            >
              {SECTION_LABELS[sec]}
            </button>
          ))}
        </nav>

        {/* Metadata info */}
        <div className="mx-3 mt-8 p-3 rounded-xl bg-neutral-950 border border-neutral-900 text-[10px] space-y-2">
          <div>
            <div className="text-neutral-500 font-mono">Run ID</div>
            <div className="font-mono text-neutral-300 truncate">{MOCK_REPORT.run_id}</div>
          </div>
          <div>
            <div className="text-neutral-500 font-mono">World Model</div>
            <div className="font-mono text-neutral-300">{MOCK_REPORT.world_model_version}</div>
          </div>
          <div>
            <div className="text-neutral-500 font-mono">Population</div>
            <div className="text-neutral-300">{MOCK_REPORT.population_size.toLocaleString()} 人 ({MOCK_REPORT.mc_rounds} 轮)</div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto p-8 space-y-8 max-w-5xl">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-6 border-b border-neutral-900">
          <div>
            <div className="eyebrow mb-1">Market Twin Report</div>
            <h1 className="text-2xl font-light text-white tracking-tight">{MOCK_REPORT.study_name}</h1>
            <p className="text-xs text-neutral-400 font-light mt-1">
              生成时间: 2026-07-20 11:30 · 结果基于 30,000 人合成市场模拟
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button className="btn-lazzor-secondary text-xs py-1.5 px-3">
              <Share2 size={13} /> 分享
            </button>
            <button className="btn-lazzor-primary text-xs py-1.5 px-3">
              <Download size={13} /> 下载 PDF
            </button>
          </div>
        </div>

        {/* Dynamic section rendering */}
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

// ─────────────────────────────────────────
// Sections
// ─────────────────────────────────────────
function ExecutiveSummarySection() {
  const { executive } = MOCK_REPORT;
  return (
    <div className="space-y-6">
      {/* Judgment Banner */}
      <Card className="bg-[#0f0f0f] border-neutral-800">
        <div className="flex items-start gap-4">
          <div className="w-8 h-8 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-xs shrink-0 mt-0.5">
            ✓
          </div>
          <div>
            <div className="eyebrow mb-1">Executive Conclusion</div>
            <h2 className="text-base font-semibold text-white tracking-tight mb-1">总体评估与建议</h2>
            <p className="text-xs text-neutral-300 font-light leading-relaxed">{executive.recommendation}</p>
          </div>
        </div>
      </Card>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {executive.key_metrics.map((m, i) => (
          <Card key={i} className="text-center">
            <div className="text-3xl font-light text-white tracking-tight">{formatPercent(m.value)}</div>
            <div className="text-xs text-neutral-400 font-light mt-1">{m.label}</div>
            <div className="text-[10px] text-neutral-500 font-mono mt-0.5">
              [{formatPercent(m.ci[0])} – {formatPercent(m.ci[1])}]
            </div>
          </Card>
        ))}
      </div>

      {/* 3 Key Insights */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <InsightCard title="最佳目标人群" content={executive.best_audience} />
        <InsightCard title="主要阻力与风险" content={executive.main_barrier} />
        <InsightCard title="推荐最优方案" content={executive.best_scenario} />
      </div>

      {/* Action Plan */}
      <Card>
        <div className="eyebrow mb-3">Priority Actions</div>
        <h3 className="text-sm font-semibold text-white mb-4">下一步优先行动建议</h3>
        <div className="space-y-3">
          {executive.next_steps.map((step, i) => (
            <div key={i} className="flex items-start gap-3 text-xs text-neutral-300 font-light">
              <span className="w-5 h-5 rounded-full bg-neutral-900 border border-neutral-800 flex items-center justify-center text-[10px] font-mono font-medium text-neutral-400 shrink-0">
                0{i + 1}
              </span>
              <span className="pt-0.5 leading-relaxed">{step}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function MarketResponseSection() {
  const { funnel } = MOCK_REPORT;
  const max = funnel[0].value;

  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Conversion Funnel</div>
        <h2 className="text-base font-semibold text-white tracking-tight">市场反应转化漏斗</h2>
      </div>

      <Card>
        <div className="space-y-3">
          {funnel.map((f, i) => (
            <div key={i} className="space-y-1">
              <div className="flex justify-between text-xs font-light">
                <span className="text-neutral-400">{f.label} · <span className="text-white">{f.stage}</span></span>
                <span className="font-mono text-neutral-200">
                  {f.value.toLocaleString()} ({formatPercent(f.value / max)})
                </span>
              </div>
              <div className="h-4 rounded bg-neutral-900 overflow-hidden p-0.5">
                <div
                  className="h-full bg-white rounded-sm transition-all duration-500"
                  style={{
                    width: `${(f.value / max) * 100}%`,
                    opacity: 0.5 + (i / funnel.length) * 0.5,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function SegmentsSection() {
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Demographics</div>
        <h2 className="text-base font-semibold text-white tracking-tight">细分人群转化表现</h2>
      </div>

      <div className="space-y-3">
        {MOCK_REPORT.segments.map((seg, i) => (
          <Card key={i}>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <span className="font-semibold text-sm text-white">{seg.name}</span>
                  <span className="text-xs text-neutral-500 font-mono">占比 {formatPercent(seg.size)}</span>
                </div>
                {seg.drivers.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {seg.drivers.map(d => (
                      <span key={d} className="status-pill text-[10px] bg-emerald-500/10 text-emerald-400 border-emerald-500/20">
                        + {d}
                      </span>
                    ))}
                    {seg.barriers.map(b => (
                      <span key={b} className="status-pill text-[10px] bg-rose-500/10 text-rose-400 border-rose-500/20">
                        - {b}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <span className="text-xs text-neutral-400 font-light">购买意向</span>
                <span className="text-lg font-light text-white font-mono">{formatPercent(seg.purchase_rate)}</span>
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
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Scenario Benchmarking</div>
        <h2 className="text-base font-semibold text-white tracking-tight">经营与定价情景对比</h2>
      </div>

      <Card>
        <div className="h-64 pt-4">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={MOCK_REPORT.scenarios} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
              <XAxis dataKey="name" tick={{ fill: "#86868b", fontSize: 10 }} />
              <YAxis tick={{ fill: "#86868b", fontSize: 10 }} />
              <Tooltip
                contentStyle={{ background: "#0a0a0a", border: "1px solid #262626", borderRadius: 8, color: "#f5f5f7", fontSize: 12 }}
              />
              <Bar dataKey="purchase_rate" name="购买意向率" fill="#ffffff" radius={[4, 4, 0, 0]} />
              <Bar dataKey="revenue_idx" name="预估收入指数" fill="#86868b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
          {MOCK_REPORT.scenarios.map((s, i) => (
            <div key={i} className={cn(
              "p-3 rounded-xl border text-center transition-colors",
              i === 1 ? "bg-neutral-900 border-white text-white" : "bg-black border-neutral-800 text-neutral-400"
            )}>
              <div className="text-[11px] font-medium leading-tight mb-1">{s.name}</div>
              <div className="text-sm font-semibold font-mono text-white">{formatPercent(s.purchase_rate)}</div>
              {i === 1 && <div className="text-[10px] text-emerald-400 font-mono mt-0.5">Recommended</div>}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function ConsumerVoicesSection() {
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Qualitative Feedback</div>
        <h2 className="text-base font-semibold text-white tracking-tight">代表性 AI 消费者声音</h2>
      </div>

      <div className="p-4 rounded-xl bg-neutral-900 border border-neutral-800 flex items-start gap-3">
        <AlertTriangle size={15} className="text-amber-400 shrink-0 mt-0.5" />
        <p className="text-xs text-neutral-300 font-light leading-relaxed">
          声明：以下内容由代表性合成消费者生成，用于解释群体行为，不是真人访谈记录。
        </p>
      </div>

      <div className="space-y-4">
        {MOCK_REPORT.consumer_voices.map((v, i) => (
          <Card key={i}>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-neutral-400">
                <span className="font-medium text-neutral-200">{v.persona}</span>
                <span className="font-mono text-neutral-500">{v.segment}</span>
              </div>
              <blockquote className="text-sm text-white font-light italic border-l-2 border-white pl-3 py-1">
                &ldquo;{v.quote}&rdquo;
              </blockquote>
              <p className="text-xs text-neutral-500 font-light">{v.reasoning}</p>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function SensitivitySection() {
  const params = [
    { name: "售价 Sensitive", impact: 0.72, desc: "降价10% → 购买率 +18%" },
    { name: "品牌信任", impact: 0.68, desc: "信任+0.1 → 购买率 +12%" },
    { name: "曝光触达", impact: 0.55, desc: "曝光+20% → 考虑率 +15%" },
    { name: "社群评分", impact: 0.41, desc: "评分4.5→5.0 → 转化率 +8%" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Sensitivity Analysis</div>
        <h2 className="text-base font-semibold text-white tracking-tight">关键参数敏感性说明</h2>
      </div>

      <Card>
        <div className="space-y-4">
          {params.map((p, i) => (
            <div key={i} className="space-y-1">
              <div className="flex justify-between text-xs font-light">
                <span className="text-white font-medium">{p.name}</span>
                <span className="text-neutral-400">{p.desc}</span>
              </div>
              <div className="h-1.5 bg-neutral-900 rounded-full overflow-hidden">
                <div className="h-full bg-white rounded-full" style={{ width: `${p.impact * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function MethodologySection() {
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Methodology & Lineage</div>
        <h2 className="text-base font-semibold text-white tracking-tight">数据血缘与方法附录</h2>
      </div>

      <Card>
        <div className="space-y-4 text-xs text-neutral-300 font-light leading-relaxed">
          <p><strong className="text-white font-semibold">1. 合成人口：</strong> 使用 TH-WORLD-2026.07.1 数据集，生成 30,000 名泰国合成居民与游客。变量之间关联，与官方统计边际分布一致。</p>
          <p><strong className="text-white font-semibold">2. 代表消费者：</strong> 群体聚类后提取代表 Agent（Centroid / High Affinity / Skeptical），由 LLM 产生结构化反应。</p>
          <p><strong className="text-white font-semibold">3. Monte Carlo 模拟：</strong> 进行了 50 轮随机采样模拟，涵盖曝光、选择效用与传播分布。</p>
          <p><strong className="text-white font-semibold">4. 数据可追溯：</strong> 本报告数据来自 Run ID <code className="text-white font-mono bg-neutral-900 px-1 py-0.5 rounded">{MOCK_REPORT.run_id}</code>。</p>
        </div>
      </Card>
    </div>
  );
}

function InsightCard({ title, content }: { title: string; content: string }) {
  return (
    <Card>
      <div className="eyebrow mb-1">{title}</div>
      <p className="text-xs text-neutral-200 font-light leading-relaxed">{content}</p>
    </Card>
  );
}
