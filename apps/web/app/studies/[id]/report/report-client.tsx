"use client";

import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, LineChart, Line,
} from "recharts";
import { AlertTriangle, Download, Share2, MapPin, ShoppingBag } from "lucide-react";
import { Card } from "@/components/ui";
import { cn, formatPercent } from "@/lib/utils";

interface ReportData {
  study_name: string;
  study_type?: string;
  run_id: string;
  world_model_version: string;
  simulation_model_version: string;
  category_key?: string;
  population_size: number;
  category_eligible_population?: number;
  model_sample_size?: number;
  mc_rounds: number;
  generated_at: string;
  calibration_status?: string;
  executive_summary: {
    recommendation: string;
    best_audience: string;
    main_barrier: string;
    best_scenario: string;
    next_steps: string[];
    key_metrics: { label: string; value: number; ci: number[]; interval_type?: string }[];
  };
  funnel: { stage: string; label: string; value: number; rate?: number }[];
  segments: {
    segment_id?: string;
    name: string;
    size: number;
    purchase_rate: number;
    drivers: string[];
    barriers: string[];
    preferred_channel?: string;
  }[];
  price_elasticity: { price: number; purchase_rate: number; revenue_idx: number; purchase_p10?: number; purchase_p90?: number }[];
  scenarios: { name: string; purchase_rate: number; revenue_idx: number; margin_idx: number; purchase_p10?: number; purchase_p90?: number }[];
  regional_breakdown: { region: string; share: string; purchase_rate: number; readiness: string }[];
  channels: {
    channel: string;
    fit_score: number;
    relative_purchase_index?: number;
    conversion?: string;
    recommendation: string;
    method?: string;
  }[];
  consumer_voices: {
    persona: string;
    segment: string;
    sentiment: string;
    quote: string;
    reasoning: string;
    price_reaction?: string;
    preferred_channel?: string;
  }[];
  implied_wtp?: { attribute: string; score_increase: number; implied_wtp_thb: number; status: string }[];
  geo_analysis?: {
    dataset_id?: string;
    venue_type: string;
    locations: Array<{
      id: string;
      name: string;
      matched_zone?: string | null;
      latitude?: number | null;
      longitude?: number | null;
      coordinate_status: string;
      observed_poi: Record<string, number>;
      observed_poi_status: string;
      target_audience_index: number;
      tourism_index: number;
      access_index: number;
      parking_index: number;
      market_activity_index: number;
      competition_saturation_index: number;
      site_score: number;
      rank: number;
    }>;
    heatmap: Array<{
      latitude: number;
      longitude: number;
      intensity: number;
      data_class: string;
    }>;
    catchments: Array<{
      minutes: number;
      radius_km: number;
      mode: string;
      data_class: string;
    }>;
    operations: {
      daily_visit_prior: number;
      daily_revenue_index_thb: number;
      peak_capacity_utilization: number;
      queue_risk: string;
      service_minutes_prior: number;
      status: string;
      hourly_demand: Array<{
        hour: string;
        visits: number;
        capacity_utilization: number;
        data_class: string;
      }>;
    };
    legend: Array<{ key: string; label: string; color: string }>;
    warnings: string[];
  } | null;
  commerce_analysis?: {
    marketplaces: string[];
    delivery_days: number;
    shipping_fee_thb: number;
    cod_available: boolean;
    official_store: boolean;
    checkout_trust_index: number;
    frictions: string[];
    status: string;
  } | null;
  warnings?: string[];
  model_lineage?: {
    model_family?: string;
    calibration?: {
      profile_version?: string;
      status?: string;
      claim?: string;
      limitations?: string[];
      sources?: { source_id?: string; observed?: boolean }[];
    };
    uncertainty?: { interval_type?: string; components?: string[]; validated_forecast_error?: number | null };
    agent_signal?: { status?: string; effective_weight?: number; sample_size?: number };
    category?: {
      category_key?: string;
      profile_version?: string;
      eligibility_status?: string;
      eligible_population_share?: number;
    };
  };
}

const EMPTY_REPORT: ReportData = {
  study_name: "正在加载报告",
  run_id: "—",
  world_model_version: "—",
  simulation_model_version: "—",
  population_size: 0,
  mc_rounds: 0,
  generated_at: "",
  calibration_status: "unknown",
  executive_summary: {
    recommendation: "",
    best_audience: "",
    main_barrier: "",
    best_scenario: "",
    next_steps: [],
    key_metrics: [],
  },
  funnel: [],
  segments: [],
  price_elasticity: [],
  scenarios: [],
  regional_breakdown: [],
  channels: [],
  consumer_voices: [],
};

const SECTIONS = [
  "executive_summary", "market_response", "segments",
  "price_elasticity", "scenarios", "geo", "regional", "channels",
  "consumer_voices", "sensitivity", "methodology"
] as const;

const SECTION_LABELS: Record<typeof SECTIONS[number], string> = {
  executive_summary: "执行摘要",
  market_response: "转化漏斗",
  segments: "人群分析",
  price_elasticity: "价格 / 客单价弹性",
  scenarios: "情景对比",
  geo: "地图与经营",
  regional: "区域表现",
  channels: "渠道适配",
  consumer_voices: "消费者声浪",
  sensitivity: "敏感性分析",
  methodology: "数据血缘与附录",
};

function reportTerms(data: ReportData) {
  const venue = ["VENUE_STUDY", "SITE_COMPARISON", "OPERATING_SCENARIO"].includes(data.study_type ?? "");
  const creative = data.study_type === "CREATIVE_TEST";
  return {
    intent: venue ? "到店意向率" : creative ? "行动倾向率" : "购买意向率",
    probability: venue ? "模型到店概率" : creative ? "模型行动概率" : "模型购买概率",
    scenario: venue ? "门店与经营情景对比" : creative ? "广告素材情景对比" : "产品与定价情景对比",
    channel: venue ? "获客渠道适配度评级" : creative ? "投放渠道适配度评级" : "销售渠道适配度评级",
    relative: venue ? "相对到店指数" : creative ? "相对行动指数" : "相对购买指数",
  };
}

const SENTIMENT_STYLE: Record<string, { tagClass: string; label: string }> = {
  positive: { tagClass: "tag-positive", label: "积极" },
  neutral: { tagClass: "tag-neutral", label: "中立" },
  negative: { tagClass: "tag-negative", label: "消极" },
};

const CALIBRATION_LABELS: Record<string, string> = {
  prior_only: "仅工程先验",
  official_macro_calibrated_choice_prior: "泰国官方宏观校准；选择系数待验证",
  customer_override_unvalidated: "客户数据覆盖；尚未回测",
  observed_choice_fit_unvalidated: "真实选择数据拟合；尚未回测",
  validated: "已完成历史回测",
  unknown: "未知",
};

function calibrationLabel(status?: string) {
  const value = status ?? "unknown";
  return CALIBRATION_LABELS[value] ?? value;
}

export function ReportClient({
  reportId,
  publicReportUrl,
}: {
  reportId?: string;
  publicReportUrl?: string;
}) {
  const [activeSection, setActiveSection] = useState<typeof SECTIONS[number]>("executive_summary");
  const [reportData, setReportData] = useState<ReportData>(EMPTY_REPORT);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [shareStatus, setShareStatus] = useState<string | null>(null);
  const visibleSections = reportData.geo_analysis
    ? SECTIONS
    : SECTIONS.filter(section => section !== "geo");

  const shareReport = async () => {
    try {
      const url = window.location.href;
      if (navigator.share) {
        await navigator.share({ title: reportData.study_name, url });
        setShareStatus("分享面板已打开");
      } else {
        await navigator.clipboard.writeText(url);
        setShareStatus("链接已复制");
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setShareStatus("无法分享，请复制浏览器地址");
    }
  };

  useEffect(() => {
    if (publicReportUrl) {
      (async () => {
        try {
          const response = await fetch(publicReportUrl);
          if (!response.ok) throw new Error("样例报告文件不可用");
          const data = await response.json() as ReportData;
          if (!data.executive_summary) throw new Error("样例报告数据结构不完整");
          setReportData(data);
        } catch (error) {
          setLoadError(error instanceof Error ? error.message : "样例报告加载失败");
        } finally {
          setLoading(false);
        }
      })();
      return;
    }
    if (reportId && (reportId.startsWith("rpt_") || reportId.startsWith("study_"))) {
      (async () => {
        try {
          const { getReportApi } = await import("@/lib/api-client");
          const data = await getReportApi<ReportData>(reportId);
          if (data && data.executive_summary) {
            setReportData(data);
          } else {
            throw new Error("报告数据结构不完整");
          }
        } catch (error) {
          setLoadError(error instanceof Error ? error.message : "报告加载失败");
        } finally {
          setLoading(false);
        }
      })();
    } else {
      setLoadError("缺少有效的报告编号");
      setLoading(false);
    }
  }, [reportId, publicReportUrl]);

  if (loading) {
    return (
      <div className="p-8">
        <Card>
          <div className="eyebrow mb-2">Loading Verified Report</div>
          <p className="text-sm text-neutral-300">正在从后端读取本次运行的真实报告数据…</p>
        </Card>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="p-8">
        <Card>
          <div className="eyebrow mb-2">Report Unavailable</div>
          <h2 className="text-base font-semibold text-white">报告读取失败</h2>
          <p className="text-xs text-neutral-400 mt-2">{loadError}</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* Section Nav */}
      <aside className="w-56 shrink-0 border-r border-neutral-900 bg-base py-6 sticky top-0 h-screen overflow-y-auto">
        <div className="px-4 mb-4">
          <span className="eyebrow">Report Sections</span>
        </div>
        <nav className="space-y-1 px-2">
          {visibleSections.map(sec => (
            <button
              key={sec}
              onClick={() => setActiveSection(sec)}
              className={cn(
                "w-full text-left px-3 py-2 rounded-lg text-xs font-medium transition-colors flex items-center gap-2",
                activeSection === sec
                  ? "bg-neutral-900 text-white font-semibold"
                  : "text-neutral-400 hover:text-white hover:bg-neutral-900/40"
              )}
            >
              {activeSection === sec && <span className="w-1 h-1 rounded-full bg-white shrink-0" />}
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
            <h1 className="text-2xl font-semibold text-white tracking-tight">{reportData.study_name}</h1>
            <p className="text-xs text-neutral-400 font-light mt-1">
              基于 {reportData.population_size.toLocaleString()} 泰国合成人口 · 模型样本 {(reportData.model_sample_size ?? reportData.population_size).toLocaleString()} · {reportData.mc_rounds} 轮 Monte Carlo
            </p>
            <p className="text-[10px] text-neutral-500 font-mono mt-1">
              校准：{calibrationLabel(reportData.calibration_status)} · {reportData.simulation_model_version}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button onClick={shareReport} className="btn-cmai-secondary text-xs py-1.5 px-3">
              <Share2 size={13} /> 分享
            </button>
            <button onClick={() => window.print()} className="btn-cmai-primary text-xs py-1.5 px-3">
              <Download size={13} /> 打印 / 存 PDF
            </button>
          </div>
        </div>
        {shareStatus && <p className="text-[11px] text-neutral-400 -mt-6">{shareStatus}</p>}

        {/* Sections */}
        {activeSection === "executive_summary" && <ExecutiveSummarySection data={reportData} />}
        {activeSection === "market_response" && <MarketResponseSection data={reportData} />}
        {activeSection === "segments" && <SegmentsSection data={reportData} />}
        {activeSection === "price_elasticity" && <PriceElasticitySection data={reportData} />}
        {activeSection === "scenarios" && <ScenariosSection data={reportData} />}
        {activeSection === "geo" && <GeoAnalysisSection data={reportData} />}
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
function ExecutiveSummarySection({ data }: { data: ReportData }) {
  const { executive_summary } = data;
  return (
    <div className="space-y-6">
      {/* Verdict Banner */}
      <Card>
        <div className="flex items-start gap-4">
          <div className="w-8 h-8 rounded-full bg-neutral-900 border border-neutral-800 flex items-center justify-center text-neutral-300 font-bold text-xs shrink-0 mt-0.5">
            ✓
          </div>
          <div>
            <div className="eyebrow mb-1">Strategic Conclusion</div>
            <h2 className="text-base font-semibold text-white tracking-tight mb-1">战略落地结论</h2>
            <p className="text-xs text-neutral-300 font-light leading-relaxed max-w-2xl">{executive_summary.recommendation}</p>
          </div>
        </div>
      </Card>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {executive_summary.key_metrics.map((m, i) => (
          <Card key={i} className="text-center">
            <div className="text-3xl font-semibold text-white tracking-tight">
              {formatPercent(m.value)}
            </div>
            <div className="text-xs text-neutral-400 font-light mt-1">{m.label}</div>
            <div className="text-[10px] text-neutral-500 font-mono mt-0.5">
              [{formatPercent(m.ci[0])} – {formatPercent(m.ci[1])}]
            </div>
          </Card>
        ))}
      </div>

      {/* 3 Key Insights */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <InsightCard title="最佳目标人群" tagClass="tag-positive" content={executive_summary.best_audience} />
        <InsightCard title="主要阻力与风险" tagClass="tag-negative" content={executive_summary.main_barrier} />
        <InsightCard title="推荐最优方案" tagClass="tag-neutral" content={executive_summary.best_scenario} />
      </div>

      {/* Action Plan */}
      <Card>
        <div className="eyebrow mb-3">Priority Action Plan</div>
        <h3 className="text-sm font-semibold text-white mb-4">下一步优先落地路线图</h3>
        <div className="space-y-3">
          {executive_summary.next_steps.map((step, i) => (
            <div key={i} className="flex items-start gap-3 text-xs text-neutral-300 font-light">
              <span className="w-5 h-5 rounded-full bg-neutral-900 border border-neutral-800 flex items-center justify-center text-[10px] font-mono font-medium text-neutral-300 shrink-0">
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

function MarketResponseSection({ data }: { data: ReportData }) {
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
              <div className="h-3 rounded bg-neutral-900 overflow-hidden">
                <div
                  className="h-full rounded-sm bg-neutral-200 transition-all duration-500"
                  style={{
                    width: `${(f.value / max) * 100}%`,
                    opacity: 0.3 + (i / funnel.length) * 0.7,
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

function SegmentsSection({ data }: { data: ReportData }) {
  const terms = reportTerms(data);
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
                  <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 tag-label">
                    {seg.drivers.map(d => (
                      <span key={d} className="tag-positive">+ {d}</span>
                    ))}
                    {seg.barriers.map(b => (
                      <span key={b} className="tag-negative">− {b}</span>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <span className="text-xs text-neutral-400 font-light">{terms.probability}</span>
                <span className="text-lg font-semibold text-white tabular-nums">{formatPercent(seg.purchase_rate)}</span>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function PriceElasticitySection({ data }: { data: ReportData }) {
  const elasticity = data.price_elasticity || [];
  const terms = reportTerms(data);
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Demand Curve & Pricing</div>
        <h2 className="text-base font-semibold text-white tracking-tight">价格 / 客单价响应曲线</h2>
      </div>

      <Card>
        <div className="h-64 pt-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={elasticity} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#242424" />
              <XAxis dataKey="price" tick={{ fill: "#86868b", fontSize: 11 }} label={{ value: "售价 (THB)", position: "insideBottom", offset: -5, fill: "#86868b", fontSize: 10 }} />
              <YAxis tick={{ fill: "#86868b", fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "#131313", border: "1px solid #242424", borderRadius: 8, color: "#f5f5f7", fontSize: 12 }} />
              <Line type="monotone" dataKey="purchase_rate" name={terms.intent} stroke="#6ba0ff" strokeWidth={2} dot={{ r: 3, fill: "#6ba0ff" }} />
              <Line type="monotone" dataKey="revenue_idx" name="相对收入指数" stroke="#5dd8c1" strokeWidth={2} strokeDasharray="4 4" dot={{ r: 3, fill: "#5dd8c1" }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-4 grid grid-cols-5 gap-2 text-center">
          {elasticity.map((e, i) => (
            <div key={i} className="p-2.5 rounded-lg bg-black border border-neutral-900">
              <div className="text-[10px] text-neutral-500 font-mono">THB {e.price}</div>
              <div className="text-xs font-semibold text-white mt-0.5">{formatPercent(e.purchase_rate)}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function ScenariosSection({ data }: { data: ReportData }) {
  const terms = reportTerms(data);
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Scenario Benchmarking</div>
        <h2 className="text-base font-semibold text-white tracking-tight">{terms.scenario}</h2>
      </div>

      <Card>
        <div className="h-64 pt-4">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.scenarios} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#242424" />
              <XAxis dataKey="name" tick={{ fill: "#86868b", fontSize: 10 }} />
              <YAxis tick={{ fill: "#86868b", fontSize: 10 }} />
              <Tooltip contentStyle={{ background: "#131313", border: "1px solid #242424", borderRadius: 8, color: "#f5f5f7", fontSize: 12 }} />
              <Bar dataKey="purchase_rate" name={terms.intent} fill="#6ba0ff" radius={[4, 4, 0, 0]} />
              <Bar dataKey="revenue_idx" name="相对收入指数" fill="#5dd8c1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
          {data.scenarios.map((s, i) => (
            <div key={i} className={cn(
              "p-3 rounded-xl border text-center transition-colors",
              s.name === data.executive_summary.best_scenario ? "bg-neutral-900 border-neutral-700 text-white" : "bg-black border-neutral-800 text-neutral-400"
            )}>
              <div className="text-[11px] font-medium leading-tight mb-1 whitespace-pre-line">{s.name}</div>
              <div className="text-sm font-semibold text-white">{formatPercent(s.purchase_rate)}</div>
              {s.name === data.executive_summary.best_scenario && <div className="tag-label tag-positive mt-0.5">Recommended</div>}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function GeoAnalysisSection({ data }: { data: ReportData }) {
  const geo = data.geo_analysis;
  if (!geo) {
    return (
      <Card>
        <p className="text-xs text-neutral-400">本研究不包含地理分析。</p>
      </Card>
    );
  }
  const points = geo.heatmap;
  const latitudes = points.map(point => point.latitude);
  const longitudes = points.map(point => point.longitude);
  const minLat = Math.min(...latitudes);
  const maxLat = Math.max(...latitudes);
  const minLng = Math.min(...longitudes);
  const maxLng = Math.max(...longitudes);
  const projectX = (longitude: number) => 35 + ((longitude - minLng) / Math.max(0.0001, maxLng - minLng)) * 630;
  const projectY = (latitude: number) => 345 - ((latitude - minLat) / Math.max(0.0001, maxLat - minLat)) * 310;
  const queueLabel = {
    high: "高",
    medium: "中",
    low: "低",
  }[geo.operations.queue_risk] ?? geo.operations.queue_risk;

  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Geo Demand & Venue Operations</div>
        <h2 className="text-base font-semibold text-white tracking-tight">地理需求热力图与小时经营模型</h2>
        <p className="text-xs text-neutral-400 mt-2">
          蓝色 POI 为公开观测记录；橙色热区和小时访问量为模型推算，不代表真实手机信令或门店客流。
        </p>
      </div>

      <div className="grid lg:grid-cols-[1.55fr_.75fr] gap-4">
        <Card className="overflow-hidden !p-0">
          <div className="px-5 py-4 border-b border-blue-400/10 flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-xs font-semibold text-white">候选点与模型需求热区</div>
              <div className="text-[10px] text-neutral-500 font-mono mt-1">{geo.dataset_id ?? "unversioned"}</div>
            </div>
            <div className="flex flex-wrap gap-3">
              {geo.legend.map(item => (
                <span key={item.key} className="flex items-center gap-1.5 text-[10px] text-neutral-400">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
                  {item.label}
                </span>
              ))}
            </div>
          </div>
          {points.length > 0 ? (
            <svg viewBox="0 0 700 380" className="w-full h-auto bg-[#050a13]" role="img" aria-label="模型需求热力图">
              <defs>
                <pattern id="geo-grid" width="50" height="50" patternUnits="userSpaceOnUse">
                  <path d="M 50 0 L 0 0 0 50" fill="none" stroke="#17243a" strokeWidth="1" />
                </pattern>
                <filter id="heat-blur"><feGaussianBlur stdDeviation="13" /></filter>
              </defs>
              <rect width="700" height="380" fill="url(#geo-grid)" />
              {points.map((point, index) => (
                <circle
                  key={index}
                  cx={projectX(point.longitude)}
                  cy={projectY(point.latitude)}
                  r={8 + point.intensity * 0.18}
                  fill="#ff9f43"
                  opacity={0.04 + point.intensity / 180}
                  filter="url(#heat-blur)"
                />
              ))}
              {geo.locations.filter(location => location.latitude != null && location.longitude != null).map(location => (
                <g key={location.id} transform={`translate(${projectX(Number(location.longitude))},${projectY(Number(location.latitude))})`}>
                  <circle r="13" fill="#07101f" stroke="#6ba0ff" strokeWidth="2" />
                  <circle r="4" fill="#6ba0ff" />
                  <text y="-19" textAnchor="middle" fill="#f8fafc" fontSize="10">{location.rank}. {location.matched_zone || location.name}</text>
                </g>
              ))}
            </svg>
          ) : (
            <div className="h-72 flex items-center justify-center text-xs text-neutral-500">
              缺少可解析坐标，无法绘制热力图；请补充经纬度。
            </div>
          )}
          <div className="px-5 py-3 border-t border-blue-400/10 flex flex-wrap gap-2">
            {geo.catchments.map(item => (
              <span key={item.minutes} className="text-[10px] px-2.5 py-1 rounded-full bg-orange-400/10 text-orange-200 border border-orange-300/10">
                步行 {item.minutes} 分钟 ≈ {item.radius_km} km · 半径代理
              </span>
            ))}
          </div>
        </Card>

        <div className="space-y-3">
          {geo.locations.map(location => (
            <Card key={location.id} className={location.rank === 1 ? "border-blue-400/30" : ""}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <span className="eyebrow">Rank 0{location.rank}</span>
                  <h3 className="text-sm font-semibold text-white mt-1">{location.name}</h3>
                  <p className="text-[10px] text-neutral-500 mt-1">
                    {location.coordinate_status === "resolved" ? `${location.latitude}, ${location.longitude}` : "坐标缺失"}
                  </p>
                </div>
                <div className="text-2xl font-semibold text-blue-200">{location.site_score}</div>
              </div>
              <div className="grid grid-cols-2 gap-2 mt-4 text-[10px]">
                <div className="rounded-lg bg-black/40 p-2 text-neutral-400">目标客群 <strong className="block text-white text-xs mt-0.5">{location.target_audience_index}</strong></div>
                <div className="rounded-lg bg-black/40 p-2 text-neutral-400">交通便利 <strong className="block text-white text-xs mt-0.5">{location.access_index}</strong></div>
                <div className="rounded-lg bg-black/40 p-2 text-neutral-400">市场活跃 <strong className="block text-white text-xs mt-0.5">{location.market_activity_index}</strong></div>
                <div className="rounded-lg bg-black/40 p-2 text-neutral-400">竞争饱和 <strong className="block text-white text-xs mt-0.5">{location.competition_saturation_index}</strong></div>
              </div>
              <div className="mt-3 text-[10px] text-neutral-500">
                POI：{location.observed_poi_status === "public_snapshot"
                  ? Object.entries(location.observed_poi).map(([key, value]) => `${key} ${value}`).join(" · ")
                  : "未观测，当前使用行业先验"}
              </div>
            </Card>
          ))}
        </div>
      </div>

      <div className="grid lg:grid-cols-[1.5fr_.5fr] gap-4">
        <Card>
          <div className="eyebrow mb-1">Hourly demand prior</div>
          <h3 className="text-sm font-semibold text-white">小时访问与容量占用</h3>
          <div className="h-64 mt-5">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={geo.operations.hourly_demand}>
                <CartesianGrid strokeDasharray="3 3" stroke="#17243a" />
                <XAxis dataKey="hour" tick={{ fill: "#8793a8", fontSize: 10 }} />
                <YAxis tick={{ fill: "#8793a8", fontSize: 10 }} />
                <Tooltip contentStyle={{ background: "#091120", border: "1px solid #213456", borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="visits" name="模型访问量" fill="#6ba0ff" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <div className="grid grid-cols-2 lg:grid-cols-1 gap-3">
          <Card><span className="eyebrow">日访问先验</span><div className="text-2xl font-semibold text-white mt-2">{geo.operations.daily_visit_prior}</div></Card>
          <Card><span className="eyebrow">相对日收入</span><div className="text-2xl font-semibold text-white mt-2">฿{geo.operations.daily_revenue_index_thb.toLocaleString()}</div></Card>
          <Card><span className="eyebrow">峰值容量</span><div className="text-2xl font-semibold text-white mt-2">{formatPercent(geo.operations.peak_capacity_utilization)}</div></Card>
          <Card><span className="eyebrow">排队风险</span><div className="text-2xl font-semibold text-white mt-2">{queueLabel}</div></Card>
        </div>
      </div>
    </div>
  );
}

function RegionalSection({ data }: { data: ReportData }) {
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
                <span className={cn("text-[10px] px-2 py-0.5 rounded font-mono bg-neutral-900", r.readiness === "高" ? "text-neutral-100" : "text-neutral-400")}>
                  模型相对倾向: {r.readiness}
                </span>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function ChannelsSection({ data }: { data: ReportData }) {
  const channels = data.channels || [];
  const terms = reportTerms(data);
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Distribution Fit</div>
        <h2 className="text-base font-semibold text-white tracking-tight">{terms.channel}</h2>
      </div>

      {data.commerce_analysis && (
        <Card className="border-blue-400/20">
          <div className="grid sm:grid-cols-[1fr_auto] gap-5">
            <div>
              <span className="eyebrow text-blue-300">Ecommerce checkout context</span>
              <h3 className="text-sm font-semibold text-white mt-1">泰国电商履约与信任诊断</h3>
              <div className="flex flex-wrap gap-2 mt-3">
                {data.commerce_analysis.marketplaces.map(item => (
                  <span key={item} className="text-[10px] px-2 py-1 rounded-full bg-blue-400/10 text-blue-200">{item}</span>
                ))}
              </div>
              <p className="text-xs text-neutral-400 mt-3">
                运费 ฿{data.commerce_analysis.shipping_fee_thb} · 约 {data.commerce_analysis.delivery_days} 天送达 ·
                COD {data.commerce_analysis.cod_available ? "支持" : "不支持"} ·
                官方店 {data.commerce_analysis.official_store ? "有" : "无"}
              </p>
              <p className="text-[10px] text-neutral-500 mt-2">
                {data.commerce_analysis.frictions.length
                  ? `主要阻力：${data.commerce_analysis.frictions.join("；")}`
                  : "当前未识别明显结账与履约阻力。"}
              </p>
            </div>
            <div className="sm:text-right">
              <span className="eyebrow">结账信任指数</span>
              <div className="text-4xl font-semibold text-blue-200 mt-2">{data.commerce_analysis.checkout_trust_index}</div>
              <div className="text-[10px] text-neutral-500 mt-1">结构化先验 / 100</div>
            </div>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {channels.map((c, i) => (
          <Card key={i}>
            <div className="flex items-start gap-3">
              <ShoppingBag size={18} className="text-neutral-500 shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-xs text-white">{c.channel}</span>
                  <span className="text-xs font-mono text-neutral-300">匹配度 {c.fit_score}/100</span>
                </div>
                <p className="text-xs text-neutral-400 font-light leading-relaxed">{c.recommendation}</p>
                <div className="mt-2 text-[10px] text-neutral-500 font-mono">
                  {c.relative_purchase_index !== undefined
                    ? `${terms.relative}: ${c.relative_purchase_index}（总体基准 = 100）`
                    : `模型渠道值: ${c.conversion ?? "未记录"}`}
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function ConsumerVoicesSection({ data }: { data: ReportData }) {
  const terms = reportTerms(data);
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Qualitative Feedback Panel</div>
        <h2 className="text-base font-semibold text-white tracking-tight">LLM 结构化解释样本</h2>
      </div>

      <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-900 flex items-start gap-3">
        <AlertTriangle size={15} className="text-neutral-500 shrink-0 mt-0.5" />
        <p className="text-xs text-neutral-300 font-light leading-relaxed">
          声明：以下内容由代表性合成记录结合 Gemini 生成，只用于提出可验证的理由与阻碍假设，不是真人访谈记录，也不直接决定{terms.probability}。
        </p>
      </div>

      <div className="space-y-4">
        {data.consumer_voices.length === 0 && (
          <Card>
            <p className="text-xs text-neutral-400">
              本次运行没有可验证的 LLM 代表样本输出，因此未展示虚构 Persona，且定量结果未受到 LLM 影响。
            </p>
          </Card>
        )}
        {data.consumer_voices.map((v, i) => {
          const s = SENTIMENT_STYLE[v.sentiment] ?? SENTIMENT_STYLE.neutral;
          return (
            <Card key={i}>
              <div className="space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-xs">
                  <span className="font-medium text-white">{v.persona}</span>
                  <div className="flex items-center gap-3">
                    <span className={cn("tag-label", s.tagClass)}>{s.label}</span>
                    <span className="font-mono text-neutral-500">{v.segment}</span>
                    {v.preferred_channel && (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-neutral-900 text-neutral-400 border border-neutral-800">
                        {v.preferred_channel}
                      </span>
                    )}
                  </div>
                </div>
                <blockquote className="text-sm text-white font-light italic pl-3 py-1 border-l border-neutral-700">
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
          );
        })}
      </div>
    </div>
  );
}

function SensitivitySection({ data }: { data: ReportData }) {
  const elasticity = data.price_elasticity || [];
  const midpoint = elasticity.length > 0 ? elasticity[Math.floor(elasticity.length / 2)] : null;
  const params = (data.implied_wtp || []).map(item => ({
    name: item.attribute,
    impact: Math.min(1, Math.abs(item.implied_wtp_thb) / Math.max(1, midpoint?.price ?? 1)),
    desc: `属性评分 +${item.score_increase.toFixed(1)} 的先验隐含 WTP：THB ${item.implied_wtp_thb.toFixed(2)}`,
  }));
  if (midpoint && elasticity.length >= 3) {
    const lower = elasticity[Math.max(0, Math.floor(elasticity.length / 2) - 1)];
    params.unshift({
      name: "售价",
      impact: Math.min(1, Math.abs(lower.purchase_rate - midpoint.purchase_rate) / Math.max(0.01, midpoint.purchase_rate)),
      desc: `THB ${midpoint.price} → THB ${lower.price}，模型购买概率 ${formatPercent(midpoint.purchase_rate)} → ${formatPercent(lower.purchase_rate)}`,
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Sensitivity Analysis</div>
        <h2 className="text-base font-semibold text-white tracking-tight">关键参数敏感性说明</h2>
      </div>

      <Card>
        <div className="space-y-4">
          {params.length === 0 && (
            <p className="text-xs text-neutral-400">本套餐未生成敏感性或 WTP 结果。</p>
          )}
          {params.map((p, i) => (
            <div key={i} className="space-y-1">
              <div className="flex justify-between text-xs font-light">
                <span className="text-white font-medium">{p.name}</span>
                <span className="text-neutral-400">{p.desc}</span>
              </div>
              <div className="h-1.5 bg-neutral-900 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full bg-neutral-200"
                  style={{ width: `${p.impact * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function MethodologySection({ data }: { data: ReportData }) {
  const calibration = data.model_lineage?.calibration;
  const uncertainty = data.model_lineage?.uncertainty;
  const agentSignal = data.model_lineage?.agent_signal;
  const category = data.model_lineage?.category;
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">Methodology & Lineage</div>
        <h2 className="text-base font-semibold text-white tracking-tight">数据血缘与方法附录</h2>
      </div>

      <Card>
        <div className="space-y-4 text-xs text-neutral-300 font-light leading-relaxed">
          <p><strong className="text-white font-semibold">1. 校准状态：</strong> {calibrationLabel(calibration?.status ?? data.calibration_status)}。{calibration?.claim ?? "未提供校准声明。"}</p>
          <p><strong className="text-white font-semibold">2. 选择模型：</strong> {data.model_lineage?.model_family ?? "未记录"}；包含焦点方案、竞品方案与不购买选项，不以 LLM 投票直接计算市场规模。</p>
          <p><strong className="text-white font-semibold">3. 不确定性：</strong> {uncertainty?.interval_type ?? "未记录"}；组成包括 {(uncertainty?.components ?? []).join("、") || "未记录"}。历史回测误差：{uncertainty?.validated_forecast_error ?? "尚未建立"}。</p>
          <p><strong className="text-white font-semibold">4. LLM 信号：</strong> 状态 {agentSignal?.status ?? "not_used"}，有效权重 {agentSignal?.effective_weight ?? 0}，完成代表样本 {agentSignal?.sample_size ?? 0}。不可用时不会替换为固定 Persona。</p>
          <p><strong className="text-white font-semibold">5. 品类人群：</strong> {category?.category_key ?? data.category_key ?? "通用消费品"}；目标人群占总体 {formatPercent(category?.eligible_population_share ?? 1)}，资格口径为 {category?.eligibility_status ?? "通用人群假设"}。</p>
          <p><strong className="text-white font-semibold">6. 数据可追溯：</strong> 已记录 {(calibration?.sources ?? []).filter(source => source.observed).length} 个观测数据源；本报告来自 Run ID <code className="text-white font-mono bg-neutral-900 px-1 py-0.5 rounded">{data.run_id}</code>。</p>
          {(data.warnings || []).map((warning, index) => (
            <p key={index} className="text-neutral-500">限制 {index + 1}：{warning}</p>
          ))}
        </div>
      </Card>
    </div>
  );
}

function InsightCard({ title, content, tagClass }: { title: string; content: string; tagClass?: string }) {
  return (
    <Card>
      <div className="eyebrow mb-1">{title}</div>
      <p className="text-xs text-neutral-200 font-light leading-relaxed">{content}</p>
      {tagClass && <span className={cn("tag-label mt-2 inline-block", tagClass)}>●</span>}
    </Card>
  );
}
