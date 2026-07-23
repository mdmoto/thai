"use client";

import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, LineChart, Line,
} from "recharts";
import { Info, ChevronDown, ChevronUp, AlertTriangle, Download, Share2, MapPin, ShoppingBag } from "lucide-react";
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
  executive_summary: {
    recommendation: "✅ 方案值得推进。建议售价调整至 THB 249，并优先在 Shopee/Lazada 旗舰店主推，可获得最佳投资回报率与市场份额。",
    best_audience: "25-35岁大曼谷/清迈区域中高收入女性群体，养宠物，月收入 3-6 万泰铢",
    main_barrier: "品牌初始知名度较低（72%受访人口未听说过），对在线支付与跨境物流时效存有顾虑",
    best_scenario: "方案B：售价下调 10% + Lazada/Shopee 官方旗舰店首发",
    next_steps: [
      "优先在 Shopee 泰国与 Lazada 开启官方店铺，建立品类口碑页面",
      "将首发促销价格设置为 THB 249（比标准定价 299 优惠 16%），吸引早期尝鲜人群",
      "合作 10-15 名清迈/曼谷本土生活方式 KOL 制作开箱与实际体验短视频",
      "建立本地仓发货（Bangkok Warehousing），将物流履约时间缩短至 48 小时以内"
    ],
    key_metrics: [
      { label: "总体购买意向率", value: 0.287, ci: [0.241, 0.334] },
      { label: "目标触达认知率", value: 0.43, ci: [0.38, 0.49] },
      { label: "价格区间接受度", value: 0.61, ci: [0.54, 0.68] },
      { label: "预测 90 天复购率", value: 0.52, ci: [0.44, 0.61] },
    ],
  },
  funnel: [
    { stage: "目标人群总数", label: "Eligible Population", value: 30000 },
    { stage: "广告曝光触达", label: "Exposed", value: 12900 },
    { stage: "引起注意关注", label: "Noticed", value: 7224 },
    { stage: "理解产品价值", label: "Understood", value: 5779 },
    { stage: "产生购买兴趣", label: "Interested", value: 3668 },
    { stage: "建立品牌信任", label: "Trusted", value: 2057 },
    { stage: "加入考虑清单", label: "Considered", value: 1131 },
    { stage: "完成首单购买", label: "Purchased", value: 860 },
  ],
  segments: [
    { name: "都市白领消费人群", size: 0.35, purchase_rate: 0.38, drivers: ["品质感", "设计精美"], barriers: ["品牌陌生"], preferred_channel: "Lazada / Shopee" },
    { name: "年轻单身潮流受众", size: 0.28, purchase_rate: 0.31, drivers: ["新奇有趣", "社交推荐"], barriers: ["价格敏感"], preferred_channel: "TikTok Shop" },
    { name: "宠物专属主妇", size: 0.22, purchase_rate: 0.42, drivers: ["方便购买", "成分安全"], barriers: ["价格略高"], preferred_channel: "Shopee Mall" },
    { name: "区域外省家庭人口", size: 0.15, purchase_rate: 0.12, drivers: ["促销折扣"], barriers: ["运费高", "网购习惯弱"], preferred_channel: "线下连锁" },
  ],
  price_elasticity: [
    { price: 209, purchase_rate: 0.396, revenue_idx: 96.6 },
    { price: 254, purchase_rate: 0.339, revenue_idx: 100.3 },
    { price: 299, purchase_rate: 0.287, revenue_idx: 100.0 },
    { price: 344, purchase_rate: 0.235, revenue_idx: 94.3 },
    { price: 389, purchase_rate: 0.186, revenue_idx: 84.5 },
  ],
  scenarios: [
    { name: "基准方案 A\nTHB 299 / 全渠道", purchase_rate: 0.287, revenue_idx: 100, margin_idx: 100 },
    { name: "方案 B\nTHB 249 / Lazada 主推", purchase_rate: 0.341, revenue_idx: 97, margin_idx: 88 },
    { name: "方案 C\nTHB 339 / 高端定位", purchase_rate: 0.198, revenue_idx: 96, margin_idx: 118 },
    { name: "方案 D\nTHB 299 / 全渠道 + KOL", purchase_rate: 0.318, revenue_idx: 108, margin_idx: 102 },
  ],
  regional_breakdown: [
    { region: "大曼谷都市圈 (BKK)", share: "45%", purchase_rate: 0.358, readiness: "高" },
    { region: "清迈及北部大区", share: "20%", purchase_rate: 0.315, readiness: "中高" },
    { region: "普吉及南部沿海", share: "15%", purchase_rate: 0.272, readiness: "中" },
    { region: "春武里/东部走廊(EEC)", share: "10%", purchase_rate: 0.243, readiness: "中" },
    { region: "东北部其他省份", share: "10%", purchase_rate: 0.115, readiness: "低" },
  ],
  channels: [
    { channel: "Shopee 泰国", fit_score: 88, conversion: "4.2%", recommendation: "首选主流销售主阵地" },
    { channel: "TikTok Shop", fit_score: 84, conversion: "3.8%", recommendation: "适合年轻客群短视频爆款冲动购买" },
    { channel: "Lazada 泰国", fit_score: 81, conversion: "3.5%", recommendation: "高客单价与白领客群主力渠道" },
    { channel: "线下精品连锁/连锁超市", fit_score: 65, conversion: "1.8%", recommendation: "适合后期铺货建立品牌信任度" },
  ],
  consumer_voices: [
    {
      persona: "28岁曼谷金融外企白领，月收入6.5万铢",
      segment: "都市白领消费人群",
      sentiment: "positive",
      quote: "对包装和定位很感兴趣，如果品质确实好，THB 299 的价格完全在我的预算范围内。",
      reasoning: "注重个人生活品质与品牌美誉度，价格敏感度较低，优先看重产品功效与用户口碑。",
      price_reaction: "价格合理，符合高品质定位",
      preferred_channel: "Lazada Flagship Store"
    },
    {
      persona: "25岁清迈大学研究助理，月收入2.8万铢",
      segment: "年轻单身潮流受众",
      sentiment: "neutral",
      quote: "外观很吸引人，但THB 299 对我来说稍微贵了一点，我会等优惠活动或先看看 TikTok 上 KOL 的评测。",
      reasoning: "社群驱动型消费者，对新颖创意感兴趣，但收入中等，容易受到促销折扣与社群推荐影响。",
      price_reaction: "略高于预期，需折扣拉动",
      preferred_channel: "TikTok Shop"
    },
    {
      persona: "35岁曼谷主妇，养有2只宠物，月收入4.2万铢",
      segment: "宠物专属主妇",
      sentiment: "positive",
      quote: "成分表看起来很安全专业，如果狗狗喜欢吃，我会选择按月长期订购。",
      reasoning: "高粘性买家，最关注成分安全性与方便程度，一旦形成信任将带来极高复购价值。",
      price_reaction: "若效果好愿意支付溢价",
      preferred_channel: "Shopee Mall"
    },
    {
      persona: "42岁暖武里公务员，家庭月收入8万铢",
      segment: "区域外省家庭人口",
      sentiment: "negative",
      quote: "对新品牌缺乏信任，本地实体店有大品牌替代品，暂时不会考虑在线购买未知品牌。",
      reasoning: "传统保守型买家，品牌信任门槛高，高度依赖线下实体渠道或熟人推荐。",
      price_reaction: "偏高，替代品丰富",
      preferred_channel: "Big C / 线下连锁"
    }
  ],
};

const SECTIONS = [
  "executive_summary", "market_response", "segments",
  "price_elasticity", "scenarios", "regional", "channels",
  "consumer_voices", "sensitivity", "methodology"
] as const;

const SECTION_LABELS: Record<typeof SECTIONS[number], string> = {
  executive_summary: "执行摘要",
  market_response: "转化漏斗",
  segments: "人群分析",
  price_elasticity: "价格弹性曲线",
  scenarios: "情景对比",
  regional: "区域表现",
  channels: "渠道适配",
  consumer_voices: "消费者声浪",
  sensitivity: "敏感性分析",
  methodology: "数据血缘与附录",
};

export function ReportClient({ studyId }: { studyId: string }) {
  const [activeSection, setActiveSection] = useState<typeof SECTIONS[number]>("executive_summary");
  const [reportData, setReportData] = useState<typeof MOCK_REPORT>(MOCK_REPORT);

  useEffect(() => {
    if (studyId && (studyId.startsWith("rpt_") || studyId.startsWith("study_"))) {
      (async () => {
        try {
          const { getReportApi } = await import("@/lib/api-client");
          const data = await getReportApi(studyId);
          if (data && data.executive_summary) {
            setReportData(prev => ({
              ...prev,
              ...data,
              study_name: data.study_name || prev.study_name,
            }));
          }
        } catch (e) {
          console.log("Using default cached report data:", e);
        }
      })();
    }
  }, [studyId]);

  return (
    <div className="flex h-full">
      {/* Section Nav */}
      <aside className="w-56 shrink-0 border-r border-neutral-900 bg-black py-6 sticky top-0 h-screen overflow-y-auto">
        <div className="px-4 mb-4">
          <span className="eyebrow">Report Sections</span>
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
            <div className="font-mono text-neutral-300 truncate">{reportData.run_id}</div>
          </div>
          <div>
            <div className="text-neutral-500 font-mono">World Model</div>
            <div className="font-mono text-neutral-300">{reportData.world_model_version}</div>
          </div>
          <div>
            <div className="text-neutral-500 font-mono">Population</div>
            <div className="text-neutral-300">{reportData.population_size.toLocaleString()} 人 ({reportData.mc_rounds} 轮)</div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto p-8 space-y-8 max-w-5xl">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-6 border-b border-neutral-900">
          <div>
            <div className="eyebrow mb-1">Thailand Digital Market Twin Report</div>
            <h1 className="text-2xl font-light text-white tracking-tight">{reportData.study_name}</h1>
            <p className="text-xs text-neutral-400 font-light mt-1">
              基于 {reportData.population_size.toLocaleString()} 泰国真实合成人口样本 · {reportData.mc_rounds} 轮 Monte Carlo 模拟
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button className="btn-cmai-secondary text-xs py-1.5 px-3">
              <Share2 size={13} /> 分享
            </button>
            <button className="btn-cmai-primary text-xs py-1.5 px-3">
              <Download size={13} /> 导出 PDF
            </button>
          </div>
        </div>

        {/* Sections */}
        {activeSection === "executive_summary" && <ExecutiveSummarySection data={reportData} />}
        {activeSection === "market_response" && <MarketResponseSection data={reportData} />}
        {activeSection === "segments" && <SegmentsSection data={reportData} />}
        {activeSection === "price_elasticity" && <PriceElasticitySection data={reportData} />}
        {activeSection === "scenarios" && <ScenariosSection data={reportData} />}
        {activeSection === "regional" && <RegionalSection data={reportData} />}
        {activeSection === "channels" && <ChannelsSection data={reportData} />}
        {activeSection === "consumer_voices" && <ConsumerVoicesSection data={reportData} />}
        {activeSection === "sensitivity" && <SensitivitySection data={reportData} />}
        {activeSection === "methodology" && <MethodologySection data={reportData} />}
      </main>
    </div>
  );
}

// ─────────────────────────────────────────
// Section Components
// ─────────────────────────────────────────
function ExecutiveSummarySection({ data }: { data: typeof MOCK_REPORT }) {
  const { executive_summary } = data;
  return (
    <div className="space-y-6">
      {/* Verdict Banner */}
      <Card className="bg-[#0c0c0c] border-neutral-800">
        <div className="flex items-start gap-4">
          <div className="w-8 h-8 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-xs shrink-0 mt-0.5">
            ✓
          </div>
          <div>
            <div className="eyebrow mb-1">Strategic Conclusion</div>
            <h2 className="text-base font-semibold text-white tracking-tight mb-1">战略落地结论</h2>
            <p className="text-xs text-neutral-300 font-light leading-relaxed">{executive_summary.recommendation}</p>
          </div>
        </div>
      </Card>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {executive_summary.key_metrics.map((m, i) => (
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
        <InsightCard title="最佳目标人群" content={executive_summary.best_audience} />
        <InsightCard title="主要阻力与风险" content={executive_summary.main_barrier} />
        <InsightCard title="推荐最优方案" content={executive_summary.best_scenario} />
      </div>

      {/* Action Plan */}
      <Card>
        <div className="eyebrow mb-3">Priority Action Plan</div>
        <h3 className="text-sm font-semibold text-white mb-4">下一步优先落地路线图</h3>
        <div className="space-y-3">
          {executive_summary.next_steps.map((step, i) => (
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

function MarketResponseSection({ data }: { data: typeof MOCK_REPORT }) {
  const { funnel } = data;
  const max = funnel[0].value;

  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Conversion Funnel</div>
        <h2 className="text-base font-semibold text-white tracking-tight">市场反应与层级转化漏斗</h2>
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
                    opacity: 0.4 + (i / funnel.length) * 0.6,
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

function SegmentsSection({ data }: { data: typeof MOCK_REPORT }) {
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Micro-Segmentation</div>
        <h2 className="text-base font-semibold text-white tracking-tight">细分人群画像与转化表现</h2>
      </div>

      <div className="space-y-3">
        {data.segments.map((seg, i) => (
          <Card key={i}>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <span className="font-semibold text-sm text-white">{seg.name}</span>
                  <span className="text-xs text-neutral-500 font-mono">占比 {formatPercent(seg.size)}</span>
                  {seg.preferred_channel && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-neutral-900 text-neutral-400 border border-neutral-800">
                      {seg.preferred_channel}
                    </span>
                  )}
                </div>
                {seg.drivers.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {seg.drivers.map(d => (
                      <span key={d} className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        + {d}
                      </span>
                    ))}
                    {seg.barriers.map(b => (
                      <span key={b} className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] bg-rose-500/10 text-rose-400 border border-rose-500/20">
                        - {b}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <span className="text-xs text-neutral-400 font-light">意向购买率</span>
                <span className="text-lg font-light text-white font-mono">{formatPercent(seg.purchase_rate)}</span>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function PriceElasticitySection({ data }: { data: typeof MOCK_REPORT }) {
  const elasticity = data.price_elasticity || [];
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Demand Curve & Pricing</div>
        <h2 className="text-base font-semibold text-white tracking-tight">价格需求弹性曲线</h2>
      </div>

      <Card>
        <div className="h-64 pt-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={elasticity} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
              <XAxis dataKey="price" tick={{ fill: "#86868b", fontSize: 11 }} label={{ value: "售价 (THB)", position: "insideBottom", offset: -5, fill: "#86868b", fontSize: 10 }} />
              <YAxis tick={{ fill: "#86868b", fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "#0a0a0a", border: "1px solid #262626", borderRadius: 8, color: "#f5f5f7", fontSize: 12 }} />
              <Line type="monotone" dataKey="purchase_rate" name="购买意向率" stroke="#ffffff" strokeWidth={2} dot={{ r: 4, fill: "#ffffff" }} />
              <Line type="monotone" dataKey="revenue_idx" name="预估营收指数" stroke="#86868b" strokeWidth={2} strokeDasharray="5 5" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-4 grid grid-cols-5 gap-2 text-center">
          {elasticity.map((e, i) => (
            <div key={i} className="p-2.5 rounded-lg bg-black border border-neutral-900">
              <div className="text-[10px] text-neutral-500 font-mono">THB {e.price}</div>
              <div className="text-xs font-semibold text-white font-mono mt-0.5">{formatPercent(e.purchase_rate)}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function ScenariosSection({ data }: { data: typeof MOCK_REPORT }) {
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Scenario Benchmarking</div>
        <h2 className="text-base font-semibold text-white tracking-tight">经营与定价情景对比</h2>
      </div>

      <Card>
        <div className="h-64 pt-4">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.scenarios} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
              <XAxis dataKey="name" tick={{ fill: "#86868b", fontSize: 10 }} />
              <YAxis tick={{ fill: "#86868b", fontSize: 10 }} />
              <Tooltip contentStyle={{ background: "#0a0a0a", border: "1px solid #262626", borderRadius: 8, color: "#f5f5f7", fontSize: 12 }} />
              <Bar dataKey="purchase_rate" name="购买意向率" fill="#ffffff" radius={[4, 4, 0, 0]} />
              <Bar dataKey="revenue_idx" name="预估收入指数" fill="#86868b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
          {data.scenarios.map((s, i) => (
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

function RegionalSection({ data }: { data: typeof MOCK_REPORT }) {
  const regions = data.regional_breakdown || [];
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Geographic Readiness</div>
        <h2 className="text-base font-semibold text-white tracking-tight">泰国各主要大区表现</h2>
      </div>

      <Card>
        <div className="space-y-3">
          {regions.map((r, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-neutral-900 last:border-0 text-xs">
              <div className="flex items-center gap-2">
                <MapPin size={14} className="text-neutral-500" />
                <span className="font-medium text-white">{r.region}</span>
                <span className="text-[10px] text-neutral-500 font-mono">占比 {r.share}</span>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-neutral-400 font-light">意向率: <strong className="text-white font-mono">{formatPercent(r.purchase_rate)}</strong></span>
                <span className={cn("text-[10px] px-2 py-0.5 rounded font-mono", r.readiness === "高" ? "bg-emerald-500/10 text-emerald-400" : "bg-neutral-900 text-neutral-400")}>
                  成熟度: {r.readiness}
                </span>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function ChannelsSection({ data }: { data: typeof MOCK_REPORT }) {
  const channels = data.channels || [];
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Distribution Fit</div>
        <h2 className="text-base font-semibold text-white tracking-tight">销售渠道适配度评级</h2>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {channels.map((c, i) => (
          <Card key={i}>
            <div className="flex items-start gap-3">
              <ShoppingBag size={18} className="text-white shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-xs text-white">{c.channel}</span>
                  <span className="text-xs font-mono text-emerald-400">匹配度 {c.fit_score}/100</span>
                </div>
                <p className="text-xs text-neutral-400 font-light leading-relaxed">{c.recommendation}</p>
                <div className="mt-2 text-[10px] text-neutral-500 font-mono">预估平均转化率: {c.conversion}</div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function ConsumerVoicesSection({ data }: { data: typeof MOCK_REPORT }) {
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Qualitative Feedback Panel</div>
        <h2 className="text-base font-semibold text-white tracking-tight">代表性 AI 消费者原声</h2>
      </div>

      <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-900 flex items-start gap-3">
        <AlertTriangle size={15} className="text-amber-400 shrink-0 mt-0.5" />
        <p className="text-xs text-neutral-300 font-light leading-relaxed">
          声明：以下内容由代表性合成消费者结合 Gemini LLM 产生，用于解释群体行为模式与买家心理，不是真人访谈记录。
        </p>
      </div>

      <div className="space-y-4">
        {data.consumer_voices.map((v, i) => (
          <Card key={i}>
            <div className="space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-xs">
                <span className="font-medium text-white">{v.persona}</span>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-neutral-500">{v.segment}</span>
                  {v.preferred_channel && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-neutral-900 text-neutral-400 border border-neutral-800">
                      {v.preferred_channel}
                    </span>
                  )}
                </div>
              </div>
              <blockquote className="text-sm text-white font-light italic border-l-2 border-white pl-3 py-1">
                &ldquo;{v.quote}&rdquo;
              </blockquote>
              <div className="p-3 rounded-lg bg-black border border-neutral-900 text-xs text-neutral-400 font-light space-y-1">
                <div><strong className="text-neutral-300 font-semibold">决策动机分析：</strong> {v.reasoning}</div>
                {v.price_reaction && (
                  <div><strong className="text-neutral-300 font-semibold">对价格反应：</strong> {v.price_reaction}</div>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function SensitivitySection({ data }: { data: typeof MOCK_REPORT }) {
  const params = [
    { name: "售价 Sensitive", impact: 0.72, desc: "售价降低10% → 购买意向率 +18%" },
    { name: "品牌信任", impact: 0.68, desc: "信任分 +0.1 → 购买意向率 +12%" },
    { name: "曝光触达", impact: 0.55, desc: "曝光率 +20% → 考虑率 +15%" },
    { name: "社群口碑评分", impact: 0.41, desc: "评分从 4.5 提升至 5.0 → 转化率 +8%" },
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

function MethodologySection({ data }: { data: typeof MOCK_REPORT }) {
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Methodology & Lineage</div>
        <h2 className="text-base font-semibold text-white tracking-tight">数据血缘与方法附录</h2>
      </div>

      <Card>
        <div className="space-y-4 text-xs text-neutral-300 font-light leading-relaxed">
          <p><strong className="text-white font-semibold">1. 合成人口：</strong> 使用 TH-WORLD-2026.07.1 数据集，生成 30,000 名泰国合成居民与游客。变量之间关联，与官方统计边际分布一致。</p>
          <p><strong className="text-white font-semibold">2. 代表消费者：</strong> 群体聚类后提取代表 Agent（Centroid / High Affinity / Skeptical），由 Gemini LLM 产生结构化反应。</p>
          <p><strong className="text-white font-semibold">3. Monte Carlo 模拟：</strong> 进行了 50 轮随机采样模拟，涵盖曝光、选择效用与传播分布。</p>
          <p><strong className="text-white font-semibold">4. 数据可追溯：</strong> 本报告数据来自 Run ID <code className="text-white font-mono bg-neutral-900 px-1 py-0.5 rounded">{data.run_id}</code>。</p>
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
