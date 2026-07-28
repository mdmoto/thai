"use client";

import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, LineChart, Line, ScatterChart, Scatter, ZAxis, Legend,
} from "recharts";
import { AlertTriangle, Download, Share2, MapPin, ShoppingBag } from "lucide-react";
import { Card } from "@/components/ui";
import { cn, formatPercent } from "@/lib/utils";
import {
  THAILAND_BOUNDARY_SOURCE,
  THAILAND_BOUNDARY_VERSION,
  THAILAND_COUNTRY_PATH,
  THAILAND_MAP_BOUNDS,
  THAILAND_PROVINCE_PATH,
} from "@/lib/thailand-boundary";

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
  sample_profile?: {
    population_size: number;
    display_sample_size: number;
    location_status: string;
    location_disclosure: string;
    points: Array<{
      person_id: string;
      age: number;
      age_group: string;
      household_income_thb: number;
      income_tier: string;
      region: string;
      province: string;
      latitude: number;
      longitude: number;
      category_eligible: boolean;
    }>;
    age_distribution: Array<{ label: string; share: number }>;
    income_distribution: Array<{ label: string; share: number }>;
    region_distribution: Array<{ label: string; share: number }>;
  };
  social_dynamics?: Array<{
    scenario_id: string;
    name: string;
    period: number;
    awareness_rate: number;
    cumulative_adoption_rate: number;
    relative_sales_index: number;
    sentiment_balance: number;
    status: string;
  }>;
  social_evidence?: {
    version: string;
    effective_date: string;
    policy: string;
    platforms: Array<{
      platform: string;
      recommended_path: string;
      public_market_scan: string;
      status: string;
      official_reference?: string | null;
    }>;
  };
  evidence_estimates?: Array<{
    topic: string;
    result: string;
    grade: string;
    basis: string;
    limitation: string;
  }>;
  evidence_acquisition?: {
    execution_policy: string;
    collectors: Array<{
      collector: string;
      status: string;
      result_count: number;
      fallback_result?: string | null;
    }>;
  };
  market_research?: {
    version: string;
    status: string;
    query?: string;
    consumer_search_query?: string;
    source_count: number;
    candidate_count?: number;
    platform_counts: Record<string, number>;
    consumer_search_queries?: string[];
    evidence_target?: {
      minimum: number;
      target: number;
      maximum: number;
      target_met: boolean;
    };
    collectors?: Array<{
      collector: string;
      status: string;
      requested: number;
      result_count: number;
      query_count?: number;
      completed_queries?: number;
      estimated_credits?: number;
      access_mode?: string;
      fallback_result?: string | null;
    }>;
    evidence: Array<{
      source_id: string;
      source_type: string;
      collector: string;
      platform: string;
      title: string;
      url: string;
      published_at?: string | null;
      collected_at: string;
      evidence_grade: string;
      content_sha256: string;
      excerpt?: string;
      observed_fields?: string[];
      evidence_role?: string;
      evidence_quality_score?: number;
      limitation: string;
    }>;
    warnings?: string[];
    usage_policy?: {
      quantitative_effect?: string;
      allowed?: string[];
      not_allowed?: string[];
    };
  };
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
    decision_journey?: {
      version?: string;
      enabled?: boolean;
      stages?: string[];
      consumer_parameter_count?: number;
      advanced_choice_parameter_count?: number;
      status?: string;
    };
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
  "sample_profile", "price_elasticity", "scenarios", "geo", "regional", "channels",
  "social_dynamics",
  "market_intelligence", "consumer_voices", "sensitivity", "methodology"
] as const;

const SECTION_LABELS: Record<typeof SECTIONS[number], string> = {
  executive_summary: "执行摘要",
  market_response: "转化漏斗",
  segments: "人群分析",
  sample_profile: "抽样分布",
  price_elasticity: "价格 / 客单价弹性",
  scenarios: "情景对比",
  geo: "地图与经营",
  regional: "区域表现",
  channels: "渠道适配",
  social_dynamics: "口碑传播",
  market_intelligence: "AI 市场情报",
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

const FUNNEL_COPY: Record<string, Record<string, { label: string; description: string }>> = {
  product: {
    eligible: { label: "符合品类条件的目标人群", description: "根据品类资格规则筛出的潜在消费者" },
    aware: { label: "已注意到产品", description: "在设定曝光条件下知道或注意到该产品" },
    understood: { label: "已理解产品卖点", description: "能够理解主要功能、价格和核心价值" },
    searched: { label: "已完成必要信息搜集", description: "结合主动检索和被动接触，取得足够信息继续决策" },
    compared: { label: "已比较产品与替代方案", description: "比较价格、功能、竞品和不购买方案" },
    trusted: { label: "已建立品牌与保障信任", description: "评价、品牌、保修和退货信息达到个人信任门槛" },
    checkout: { label: "已跨过购买摩擦", description: "跨过预算、支付、配送和退货顾虑" },
    considered: { label: "已纳入购买考虑", description: "愿意把该产品与竞品及“不购买”方案一起比较" },
    purchased: { label: "预计选择购买", description: "选择模型中最终选择本产品的期望人数" },
    repeated: { label: "购买后预计复购", description: "预计购买者中具有再次购买倾向的人数" },
    referred: { label: "购买后预计推荐", description: "预计购买者中愿意分享或推荐的人数" },
  },
  venue: {
    eligible: { label: "符合门店条件的目标客群", description: "根据门店类型、区域和消费能力筛出的潜在顾客" },
    aware: { label: "已注意到门店", description: "在设定获客条件下知道或注意到该门店" },
    understood: { label: "符合消费场景", description: "门店定位与消费者的用餐、休闲或购物场景相符" },
    searched: { label: "已完成必要信息搜集", description: "取得位置、价格、评价和营业信息" },
    compared: { label: "已比较门店与替代方案", description: "与其他门店及不出行方案进行比较" },
    trusted: { label: "已建立到店信任", description: "评价、品牌和服务保障达到个人信任门槛" },
    checkout: { label: "已跨过到店摩擦", description: "跨过时间、交通、停车和预算顾虑" },
    considered: { label: "已纳入到店考虑", description: "愿意把该门店与其他去处及“不出行”方案一起比较" },
    purchased: { label: "预计到店", description: "选择模型中最终选择到店的期望人数" },
    repeated: { label: "到店后预计再访", description: "预计到店顾客中具有再次到店倾向的人数" },
    referred: { label: "到店后预计推荐", description: "预计到店顾客中愿意分享或推荐的人数" },
  },
  creative: {
    eligible: { label: "符合投放条件的目标受众", description: "根据广告目标筛出的潜在受众" },
    aware: { label: "已触达并注意广告", description: "在设定投放条件下看到并注意到广告" },
    understood: { label: "已理解广告信息", description: "能够理解广告主张、优惠和行动指引" },
    searched: { label: "已完成必要信息搜集", description: "从广告及公开资料中取得足够信息" },
    compared: { label: "已比较主张与替代方案", description: "将广告主张与替代产品或不行动进行比较" },
    trusted: { label: "已形成可信判断", description: "素材证据和品牌信任达到个人门槛" },
    checkout: { label: "已跨过行动摩擦", description: "跨过点击、咨询、支付或到店顾虑" },
    considered: { label: "已产生行动考虑", description: "愿意进一步了解、点击或比较广告中的方案" },
    purchased: { label: "预计采取目标行动", description: "模型中预计点击、咨询或购买的期望人数" },
    repeated: { label: "预计继续互动", description: "采取行动后仍愿意持续关注或再次互动的人数" },
    referred: { label: "预计分享广告", description: "采取行动后愿意转发或推荐的人数" },
  },
};

function funnelCopy(data: ReportData, stage: string) {
  const group = ["VENUE_STUDY", "SITE_COMPARISON", "OPERATING_SCENARIO", "RESTAURANT", "CAFE", "BAR", "RETAIL"].includes(data.study_type ?? "")
    ? "venue"
    : data.study_type === "CREATIVE_TEST"
      ? "creative"
      : "product";
  return FUNNEL_COPY[group][stage] ?? {
    label: stage,
    description: "本阶段由模型按当前研究条件估计",
  };
}

const CATEGORY_LABELS: Record<string, string> = {
  PET_WATER_FOUNTAIN: "宠物智能饮水机",
  GENERAL_CONSUMER_PRODUCT: "通用消费品",
};

const MODEL_LABELS: Record<string, string> = {
  mnl_prior: "多项逻辑选择模型（MNL，当前系数为待验证先验）",
  mnl_with_observed_heterogeneity: "纳入人群差异的多项选择模型",
  hybrid_journey_mixed_logit: "多阶段消费决策旅程与随机偏好混合模型",
  mixed_logit: "混合逻辑选择模型（Mixed Logit）",
  latent_class: "潜在人群分类选择模型（Latent Class）",
  hierarchical_bayes: "分层贝叶斯联合分析模型",
};

const UNCERTAINTY_LABELS: Record<string, string> = {
  prior_predictive_p10_p90: "先验预测区间（第 10–90 百分位）",
  coefficient_prior_uncertainty: "选择系数尚未实证拟合带来的不确定性",
  observed_population_heterogeneity: "已纳入模型的人群差异",
  fixed_taste_mnl: "当前模型假定同类人群偏好结构固定",
  random_taste_heterogeneity: "已模拟个体随机偏好差异",
  multi_stage_consumer_decision_journey: "已模拟多阶段消费决策旅程",
  single_stage_choice_journey: "采用基础选择旅程",
  no_llm_quantitative_effect: "本次大模型信号未参与定量结果",
};

const STATUS_LABELS: Record<string, string> = {
  available: "可用",
  unavailable: "不可用",
  not_used: "未使用",
  disabled: "未启用",
  partial: "部分完成",
  succeeded: "采集成功",
  not_applicable: "本研究不适用",
  public_only: "仅使用公开资料",
  public_index_only_no_customer_login: "公开索引，无需客户登录",
  public_embed_or_provider_no_customer_login: "公开验证或云端数据源，无需客户登录",
  public_commerce_evidence_no_customer_login: "公开电商证据，无需客户登录",
  paid_api_access_required: "需要付费官方接口",
  api_key_and_quota_required: "需要官方接口密钥与额度",
  mixed_public_and_authorized_data: "公开证据与授权数据并用",
};

const COLLECTOR_LABELS: Record<string, string> = {
  "Thailand NSO versioned snapshots": "泰国国家统计局（NSO）版本化数据",
  "Category competitor public evidence": "品类竞品公开证据",
  "Open geospatial / POI evidence": "开放地理与周边设施数据",
  "Structured LLM research": "大模型结构化消费者研究",
  "Social platform evidence": "社交平台传播证据",
  "Crawl4AI public page reader": "公开网页深度读取",
  "Firecrawl multi-query consumer research": "泰国消费者多主题公开检索",
  "YouTube public metadata": "YouTube 公开视频资料",
  "Meta / TikTok public discovery": "Meta / TikTok 公开内容发现",
  "Lazada / Shopee public commerce evidence": "Lazada / Shopee 公开消费证据",
};

const FALLBACK_LABELS: Record<string, string> = {
  synthetic_region_distribution: "合成区域分布",
  model_segment_summary: "选择模型人群摘要",
  disclosed_social_propagation_scenarios: "已披露参数的传播情景",
  public_search_discovery: "云端公开搜索发现",
  official_api_key_or_public_url: "官方接口或公开视频网址",
  public_url_evidence_only: "仅使用公开网页证据",
  public_product_metadata_only: "仅使用公开商品元数据",
  public_pages_and_official_public_apis: "公开网页与官方公开接口",
  search_index_and_official_embed_only: "搜索索引与官方嵌入验证",
};

const SOURCE_TYPE_LABELS: Record<string, string> = {
  public_page: "直接公开页面",
  consumer_public_search: "消费者公开检索线索",
  youtube_public_metadata: "公开视频资料",
};

const PLATFORM_ACCESS_LABELS: Record<string, string> = {
  restricted_for_commercial_use: "公开市场扫描受平台商业使用规则限制",
  research_api_not_available_for_general_commercial_market_research: "研究接口不面向一般商业市场研究开放",
  paid_official_api_required: "需要付费使用官方接口",
  official_api_with_quota: "可使用官方接口，但受调用额度限制",
  transaction_and_conversion_not_public: "真实成交量与转化率不是公开数据",
};

const ATTRIBUTE_LABELS: Record<string, string> = {
  quality_score: "品质与可靠性",
  review_score: "用户评价与口碑证据",
  convenience_score: "购买与使用便利性",
  localization_score: "泰国本地化适配度",
};

const EVIDENCE_BASIS_LABELS: Record<string, string> = {
  behavioral_prior_not_officially_calibrated: "已披露的行为先验，尚未使用官方品类渗透率或真实购买数据校准",
};

const REGION_LABELS: Record<string, string> = {
  "Bangkok Metro": "曼谷都市圈",
  "East / EEC": "东部经济走廊（EEC）",
  Central: "中部地区",
  North: "北部地区",
  South: "南部地区",
  Northeast: "东北部地区",
};

function statusLabel(status?: string) {
  if (!status) return "未记录";
  return STATUS_LABELS[status] ?? status;
}

function eligibilityLabel(status?: string) {
  if (status === "behavioral_prior_not_officially_calibrated") {
    return "行为先验，尚未用官方品类渗透率或真实购买数据校准";
  }
  return status || "通用人群假设";
}

function calibrationClaim(status?: string, claim?: string) {
  if (status === "official_macro_calibrated_choice_prior") {
    return "地区人口、家庭收入区间、各府收入与支出、家庭规模等人口结构已使用泰国国家统计局公开汇总数据校准；年龄细分、消费行为特征和选择系数仍属于待验证先验。";
  }
  return claim || "未提供更详细的校准说明。";
}

function warningLabel(warning: string) {
  if (warning.includes("aggregate margins") || warning.includes("joint dependencies")) {
    return "官方输入是汇总统计，而不是逐户微观数据；年龄、收入、地区等变量之间的联合关系由系统合成。";
  }
  if (warning.includes("all ages") || warning.includes("decision population starts at age 18")) {
    return "官方地区人口占比覆盖全部年龄，而本次消费决策模拟仅纳入 18 岁及以上人群，两者统计口径不同。";
  }
  if (warning.includes("binary sex") || warning.includes("non-binary")) {
    return "泰国国家统计局当前公开口径只提供男性和女性；模型保留的 1% 非二元性别比例属于明确披露的工程假设。";
  }
  if (warning.includes("households, not individual wages")) {
    return "收入与支出数据描述的是家庭整体，不是个人工资；报告中的收入坐标均应按家庭月收入理解。";
  }
  if (warning.includes("Behavioral traits") || warning.includes("category engagement")) {
    return "消费行为特征和品类参与度尚无可直接使用的真实调查数据，目前采用可替换、可追溯的开发先验。";
  }
  if (warning.includes("Choice coefficients") || warning.includes("WTP and conversion rates")) {
    return "选择系数、支付意愿和转化率尚未使用真实订单、选择实验或广告测试数据拟合，因此只能用于方案比较，不能作为销量承诺。";
  }
  if (warning.includes("Marketplace page prices") || warning.includes("transaction volume")) {
    return "电商公开页面只能证明展示价格、评价和卖点，不能证明真实成交量、退款率或转化率。";
  }
  if (warning.includes("Forecast intervals") || warning.includes("validated forecast intervals")) {
    return "当前区间反映模型先验和人群差异，不包含历史预测误差，因此不是经过回测验证的销量置信区间。";
  }
  if (warning.includes("competitor model fields") || warning.includes("assumed_fields")) {
    return "部分竞品属性无法从公开页面确认，系统使用了已披露的字段先验；具体字段可在模型血缘记录中追溯。";
  }
  if (warning.includes("pet-ownership") || warning.includes("category sales forecast")) {
    return "品类目标人群使用尚未校准的养宠行为先验，因此购买概率不能直接解释为该品类的真实销量预测。";
  }
  if (warning.includes("LLM weak signals") || warning.includes("zero effect")) {
    return "本次大模型弱信号不可用或未启用，对任何定量结果的权重为 0；系统没有用固定虚拟人物替代。";
  }
  return warning;
}

function limitationReason(warning: string) {
  if (warning.includes("LLM weak signals")) return "运行配置：未启用模型密钥";
  if (warning.includes("microdata") || warning.includes("joint dependencies")) return "数据粒度：只有官方聚合统计";
  if (warning.includes("all ages") || warning.includes("binary sex") || warning.includes("households")) return "统计口径：官方数据定义不同";
  if (warning.includes("Behavioral traits") || warning.includes("pet-ownership")) return "缺少真实行为或品类渗透调查";
  if (warning.includes("Choice coefficients") || warning.includes("Forecast intervals")) return "缺少真实选择、销量与历史回测";
  if (warning.includes("Marketplace page") || warning.includes("competitor model fields")) return "平台公开数据不包含完整成交与转化";
  return "证据或验证尚未覆盖";
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
          <div className="eyebrow mb-2">正在读取报告</div>
          <p className="text-sm text-neutral-300">正在从后端读取本次运行的真实报告数据…</p>
        </Card>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="p-8">
        <Card>
          <div className="eyebrow mb-2">报告暂不可用</div>
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
          <span className="eyebrow">报告目录</span>
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
            <div className="text-neutral-500">本次运行编号</div>
            <div className="font-mono text-neutral-300 truncate">{reportData.run_id}</div>
          </div>
          <div>
            <div className="text-neutral-500">人口模型版本</div>
            <div className="font-mono text-neutral-300">{reportData.world_model_version}</div>
          </div>
          <div>
            <div className="text-neutral-500">AI 人群规模</div>
            <div className="text-neutral-300">{reportData.population_size.toLocaleString()} 人 ({reportData.mc_rounds} 轮)</div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto p-8 space-y-8 max-w-5xl">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-6 border-b border-neutral-900">
          <div>
            <div className="eyebrow mb-1">Chiang Mai AI Center · 商业决策报告</div>
            <h1 className="text-2xl font-semibold text-white tracking-tight">{reportData.study_name}</h1>
            <p className="text-xs text-neutral-400 font-light mt-1">
              覆盖 {reportData.population_size.toLocaleString()} 人泰国 AI 模拟消费人群 · 深度计算样本 {(reportData.model_sample_size ?? reportData.population_size).toLocaleString()} 人 · 完成 {reportData.mc_rounds} 轮风险测试
            </p>
            <p className="text-[10px] text-neutral-500 mt-1">
              AI 模拟消费人群由模型生成，不是真实问卷受访者或真实订单；人数表示模拟覆盖规模。
            </p>
            <p className="text-[10px] text-neutral-500 font-mono mt-1">
              校准：{calibrationLabel(reportData.calibration_status)} · {reportData.simulation_model_version}
            </p>
            {reportData.model_lineage?.decision_journey?.enabled && (
              <p className="text-[10px] text-cyan-200/70 mt-1">
                多阶段决策模型：{reportData.model_lineage.decision_journey.consumer_parameter_count ?? 0} 项消费者参数 ·{" "}
                {reportData.model_lineage.decision_journey.advanced_choice_parameter_count ?? 0} 项选择参数 ·{" "}
                {reportData.model_lineage.decision_journey.stages?.length ?? 0} 个决策阶段
              </p>
            )}
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
        {activeSection === "sample_profile" && <SampleProfileSection data={reportData} />}
        {activeSection === "price_elasticity" && <PriceElasticitySection data={reportData} />}
        {activeSection === "scenarios" && <ScenariosSection data={reportData} />}
        {activeSection === "geo" && <GeoAnalysisSection data={reportData} />}
        {activeSection === "regional" && <RegionalSection data={reportData} />}
        {activeSection === "channels" && <ChannelsSection data={reportData} />}
        {activeSection === "social_dynamics" && <SocialDynamicsSection data={reportData} />}
        {activeSection === "market_intelligence" && <MarketIntelligenceSection data={reportData} />}
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
            <div className="eyebrow mb-1">核心决策结论</div>
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
        <div className="eyebrow mb-3">优先行动建议</div>
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
  const eligibleStage = funnel.find(item => item.stage === "eligible");
  const purchaseStage = funnel.find(item => item.stage === "purchased");
  const eligibleBase = Math.max(1, eligibleStage?.value ?? funnel[0]?.value ?? 1);
  const purchaseBase = Math.max(1, purchaseStage?.value ?? 1);
  const mainStages = funnel.filter(item =>
    ["eligible", "aware", "understood", "considered", "purchased"].includes(item.stage),
  );
  const postPurchaseStages = funnel.filter(item =>
    ["repeated", "referred"].includes(item.stage),
  );
  const totalPopulation = Math.max(1, data.population_size);

  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">消费者转化路径</div>
        <h2 className="text-base font-semibold text-white tracking-tight">从目标人群到购买 / 到店的逐层变化</h2>
        <p className="text-xs text-neutral-400 mt-2 leading-relaxed">
          系统先从全部 {data.population_size.toLocaleString()} 人 AI 模拟消费人群中筛出符合本研究条件的目标人群，
          再估计他们经过注意、理解、考虑和最终选择的过程。人数为模型折算的期望人数，不是真实受访者数量或实际订单。
        </p>
      </div>

      <Card>
        <div className="grid grid-cols-[minmax(0,1fr)_auto_auto] gap-x-4 pb-2 border-b border-neutral-800 text-[10px] text-neutral-500">
          <span>阶段与含义</span>
          <span className="text-right">占目标人群</span>
          <span className="text-right">较上一步</span>
        </div>
        <div className="space-y-4 mt-4">
          {mainStages.map((f, i) => {
            const copy = funnelCopy(data, f.stage);
            const previous = i === 0 ? null : mainStages[i - 1];
            return (
              <div key={f.stage} className="space-y-1.5">
                <div className="grid grid-cols-[minmax(0,1fr)_auto_auto] gap-x-4 items-start">
                  <div>
                    <div className="text-xs font-medium text-white">{copy.label}</div>
                    <div className="text-[10px] text-neutral-500 mt-0.5">{copy.description}</div>
                  </div>
                  <span className="font-mono text-xs text-neutral-200 text-right whitespace-nowrap">
                    {f.value.toLocaleString()} 人<br />
                    <span className="text-[10px] text-neutral-500">{formatPercent(f.value / eligibleBase)}</span>
                  </span>
                  <span className="font-mono text-xs text-neutral-300 text-right whitespace-nowrap min-w-14">
                    {previous ? formatPercent(f.value / Math.max(1, previous.value)) : "起点"}
                  </span>
                </div>
                <div className="h-2.5 rounded bg-neutral-900 overflow-hidden">
                  <div
                    className="h-full rounded-sm bg-blue-300 transition-all duration-500"
                    style={{
                      width: `${Math.min(100, (f.value / eligibleBase) * 100)}%`,
                      opacity: 0.45 + (i / Math.max(1, mainStages.length - 1)) * 0.55,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-5 pt-4 border-t border-neutral-800 text-[11px] text-neutral-400 leading-relaxed">
          目标人群占全部 AI 模拟消费人群的 <strong className="text-white">{formatPercent((eligibleStage?.value ?? 0) / totalPopulation)}</strong>；
          最终选择占全部 AI 模拟消费人群的 <strong className="text-white">{formatPercent((purchaseStage?.value ?? 0) / totalPopulation)}</strong>。
          “占目标人群”始终以目标人群为分母，“较上一步”才表示相邻阶段的转化率。
        </div>
      </Card>

      {!!postPurchaseStages.length && (
        <div>
          <h3 className="text-sm font-semibold text-white">购买 / 到店后的两种独立结果</h3>
          <p className="text-xs text-neutral-500 mt-1">
            复购与推荐都从最终选择者开始计算，二者相互独立，并不是“先复购、再推荐”的连续步骤。
          </p>
          <div className="grid sm:grid-cols-2 gap-3 mt-3">
            {postPurchaseStages.map(f => {
              const copy = funnelCopy(data, f.stage);
              return (
                <Card key={f.stage}>
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-xs font-semibold text-white">{copy.label}</div>
                      <p className="text-[10px] text-neutral-500 mt-1 leading-relaxed">{copy.description}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-xl font-semibold text-white">{f.value.toLocaleString()} 人</div>
                      <div className="text-[10px] text-neutral-500 mt-1">
                        占最终选择者 {formatPercent(f.value / purchaseBase)}
                      </div>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      <Card className="border-amber-300/20">
        <div className="flex gap-3">
          <AlertTriangle size={16} className="text-amber-200 shrink-0 mt-0.5" />
          <p className="text-xs text-neutral-400 leading-relaxed">
            阅读提示：当前结果适合判断“哪一层流失最大”和比较不同方案。若选择系数尚未使用真实订单、选择实验或 A/B 测试回测，
            则人数和比例属于先验模型估计，不能直接作为销量或客流承诺。
          </p>
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
        <div className="eyebrow mb-1">消费者分群</div>
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
        <div className="eyebrow mb-1">需求与定价关系</div>
        <h2 className="text-base font-semibold text-white tracking-tight">价格 / 客单价响应曲线</h2>
      </div>

      <Card>
        <div className="h-64 pt-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={elasticity} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#242424" />
              <XAxis dataKey="price" tick={{ fill: "#86868b", fontSize: 11 }} label={{ value: "售价（泰铢）", position: "insideBottom", offset: -5, fill: "#86868b", fontSize: 10 }} />
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
        <div className="eyebrow mb-1">备选方案比较</div>
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
              {s.name === data.executive_summary.best_scenario && <div className="tag-label tag-positive mt-0.5">模型推荐</div>}
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
        <div className="eyebrow mb-1">地理需求与门店经营</div>
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
              <div className="text-[10px] text-neutral-500 font-mono mt-1">数据版本：{geo.dataset_id ?? "未记录"}</div>
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
                  <span className="eyebrow">综合排名第 {location.rank} 名</span>
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
                周边设施（POI）：{location.observed_poi_status === "public_snapshot"
                  ? Object.entries(location.observed_poi).map(([key, value]) => `${key} ${value}`).join(" · ")
                  : "未观测，当前使用行业先验"}
              </div>
            </Card>
          ))}
        </div>
      </div>

      <div className="grid lg:grid-cols-[1.5fr_.5fr] gap-4">
        <Card>
          <div className="eyebrow mb-1">小时需求先验估计</div>
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

function mapPoint(longitude: number, latitude: number) {
  const [minLongitude, minLatitude, maxLongitude, maxLatitude] =
    THAILAND_MAP_BOUNDS;
  return {
    x: 12 + ((longitude - minLongitude) / (maxLongitude - minLongitude)) * 336,
    y: 12 + ((maxLatitude - latitude) / (maxLatitude - minLatitude)) * 536,
  };
}

function SampleProfileSection({ data }: { data: ReportData }) {
  const sample = data.sample_profile;
  if (!sample) {
    return <Card><p className="text-xs text-neutral-400">这份旧报告尚未保存抽样可视化数据，重新运行后会自动生成。</p></Card>;
  }
  const eligible = sample.points.filter(point => point.category_eligible);
  const other = sample.points.filter(point => !point.category_eligible);
  const incomeValues = sample.points
    .map(point => point.household_income_thb)
    .sort((a, b) => a - b);
  const p95Income = incomeValues[Math.floor(incomeValues.length * 0.95)] ?? 100000;
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">AI 模拟人群分布</div>
        <h2 className="text-base font-semibold text-white tracking-tight">取样年龄、家庭收入与地域分布</h2>
        <p className="text-xs text-neutral-400 mt-2">
          从 {sample.population_size.toLocaleString()} 人 AI 模拟消费人群中分层抽取 {sample.display_sample_size.toLocaleString()} 个代表点用于展示。
        </p>
      </div>

      <div className="grid lg:grid-cols-[.78fr_1.22fr] gap-4">
        <Card>
          <div className="eyebrow mb-1">泰国样本位置分布</div>
          <h3 className="text-sm font-semibold text-white">泰国合成样本点状图</h3>
          <svg viewBox="0 0 360 560" className="w-full h-[440px] mt-4" role="img" aria-label="泰国 AI 模拟消费人群分布">
            <defs>
              <linearGradient id="thai-map-fill" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#12233d" />
                <stop offset="100%" stopColor="#08111f" />
              </linearGradient>
              <clipPath id="thailand-country-clip">
                <path d={THAILAND_COUNTRY_PATH} fillRule="evenodd" />
              </clipPath>
            </defs>
            <path
              d={THAILAND_COUNTRY_PATH}
              fill="url(#thai-map-fill)"
              fillRule="evenodd"
              stroke="#4b75aa"
              strokeWidth="1.6"
            />
            <path
              d={THAILAND_PROVINCE_PATH}
              fill="none"
              stroke="#2a456b"
              strokeWidth=".45"
              opacity=".75"
            />
            <g clipPath="url(#thailand-country-clip)">
              {other.map(point => {
                const projected = mapPoint(point.longitude, point.latitude);
                return <circle key={point.person_id} cx={projected.x} cy={projected.y} r="2.1" fill="#7c8aa1" opacity=".35" />;
              })}
              {eligible.map(point => {
                const projected = mapPoint(point.longitude, point.latitude);
                return <circle key={point.person_id} cx={projected.x} cy={projected.y} r="2.4" fill="#67d9c4" opacity=".7" />;
              })}
            </g>
          </svg>
          <div className="flex flex-wrap gap-3 text-[10px] text-neutral-400">
            <span><i className="inline-block w-2 h-2 rounded-full bg-teal-300 mr-1" />品类目标样本</span>
            <span><i className="inline-block w-2 h-2 rounded-full bg-slate-400 mr-1" />其他样本</span>
          </div>
          <p className="text-[10px] leading-relaxed text-neutral-500 mt-3">{sample.location_disclosure}</p>
          <p className="text-[9px] leading-relaxed text-neutral-600 mt-2">
            底图：{THAILAND_BOUNDARY_SOURCE} · {THAILAND_BOUNDARY_VERSION} · 泰国国界及一级行政区真实边界
          </p>
        </Card>

        <Card>
          <div className="eyebrow mb-1">年龄与家庭月收入</div>
          <h3 className="text-sm font-semibold text-white">年龄与家庭月收入坐标图</h3>
          <div className="h-[440px] mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 10, right: 18, bottom: 22, left: 18 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#17243a" />
                <XAxis type="number" dataKey="age" name="年龄" unit="岁" domain={[18, 78]} tick={{ fill: "#8793a8", fontSize: 10 }} label={{ value: "年龄", position: "bottom", fill: "#8793a8", fontSize: 11 }} />
                <YAxis type="number" dataKey="household_income_thb" name="家庭月收入" unit=" THB" domain={[0, p95Income]} tick={{ fill: "#8793a8", fontSize: 10 }} tickFormatter={value => `${Math.round(Number(value) / 1000)}k`} />
                <ZAxis range={[18, 18]} />
                <Tooltip cursor={{ strokeDasharray: "3 3" }} contentStyle={{ background: "#091120", border: "1px solid #213456", borderRadius: 8, fontSize: 11 }} formatter={(value, name) => name === "家庭月收入" ? [`฿${Number(value).toLocaleString()}`, name] : [value, name]} />
                <Legend />
                <Scatter name="品类目标样本" data={eligible.filter(point => point.household_income_thb <= p95Income)} fill="#67d9c4" fillOpacity={0.7} />
                <Scatter name="其他样本" data={other.filter(point => point.household_income_thb <= p95Income)} fill="#718096" fillOpacity={0.35} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[10px] text-neutral-500">纵轴为家庭月收入，不是个人工资；图形为保证可读性截取至样本第 95 百分位。</p>
        </Card>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <h3 className="text-sm font-semibold text-white">年龄段占比</h3>
          <div className="h-52 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sample.age_distribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="#17243a" />
                <XAxis dataKey="label" tick={{ fill: "#8793a8", fontSize: 10 }} />
                <YAxis tick={{ fill: "#8793a8", fontSize: 10 }} tickFormatter={value => `${Math.round(Number(value) * 100)}%`} />
                <Tooltip formatter={value => formatPercent(Number(value))} contentStyle={{ background: "#091120", border: "1px solid #213456", borderRadius: 8, fontSize: 11 }} />
                <Bar dataKey="share" name="样本占比" fill="#6ba0ff" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <h3 className="text-sm font-semibold text-white">家庭收入层占比</h3>
          <div className="h-52 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sample.income_distribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="#17243a" />
                <XAxis dataKey="label" tick={{ fill: "#8793a8", fontSize: 10 }} />
                <YAxis tick={{ fill: "#8793a8", fontSize: 10 }} tickFormatter={value => `${Math.round(Number(value) * 100)}%`} />
                <Tooltip formatter={value => formatPercent(Number(value))} contentStyle={{ background: "#091120", border: "1px solid #213456", borderRadius: 8, fontSize: 11 }} />
                <Bar dataKey="share" name="样本占比" fill="#c19bff" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
    </div>
  );
}

function RegionalSection({ data }: { data: ReportData }) {
  const regions = data.regional_breakdown || [];
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">区域市场表现</div>
        <h2 className="text-base font-semibold text-white tracking-tight">泰国各主要大区表现</h2>
      </div>

      <Card>
        <div className="space-y-3">
          {regions.map((r, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-neutral-900 last:border-0 text-xs">
              <div className="flex items-center gap-2">
                <MapPin size={14} className="text-neutral-500" />
                <span className="font-medium text-white">{REGION_LABELS[r.region] ?? r.region}</span>
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
        <div className="eyebrow mb-1">渠道适配分析</div>
        <h2 className="text-base font-semibold text-white tracking-tight">{terms.channel}</h2>
      </div>

      {data.commerce_analysis && (
        <Card className="border-blue-400/20">
          <div className="grid sm:grid-cols-[1fr_auto] gap-5">
            <div>
              <span className="eyebrow text-blue-300">电商下单与履约条件</span>
              <h3 className="text-sm font-semibold text-white mt-1">泰国电商履约与信任诊断</h3>
              <div className="flex flex-wrap gap-2 mt-3">
                {data.commerce_analysis.marketplaces.map(item => (
                  <span key={item} className="text-[10px] px-2 py-1 rounded-full bg-blue-400/10 text-blue-200">{item}</span>
                ))}
              </div>
              <p className="text-xs text-neutral-400 mt-3">
                运费 ฿{data.commerce_analysis.shipping_fee_thb} · 约 {data.commerce_analysis.delivery_days} 天送达 ·
                货到付款（COD）{data.commerce_analysis.cod_available ? "支持" : "不支持"} ·
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

const SOCIAL_COLORS: Record<string, string> = {
  baseline: "#8b98ad",
  ugc_showcase: "#67d9c4",
  positive_reviews: "#6ba0ff",
  creator_campaign: "#c19bff",
  negative_review_shock: "#ff7d8f",
};

function SocialDynamicsSection({ data }: { data: ReportData }) {
  const dynamics = data.social_dynamics || [];
  if (!dynamics.length) {
    return <Card><p className="text-xs text-neutral-400">这份旧报告尚未生成口碑传播情景，重新运行后会自动加入。</p></Card>;
  }
  const scenarios = Array.from(new Map(dynamics.map(item => [item.scenario_id, item.name])).entries());
  const periods = Array.from(new Set(dynamics.map(item => item.period))).sort((a, b) => a - b);
  const chartData = periods.map(period => {
    const row: Record<string, number> = { period };
    dynamics.filter(item => item.period === period).forEach(item => {
      row[item.scenario_id] = item.relative_sales_index;
    });
    return row;
  });
  const finalPeriod = Math.max(...periods);
  const finalPoints = dynamics
    .filter(item => item.period === finalPeriod)
    .sort((a, b) => b.relative_sales_index - a.relative_sales_index);

  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">口碑与社交传播</div>
        <h2 className="text-base font-semibold text-white tracking-tight">晒单、推广与评价传播情景</h2>
        <p className="text-xs text-neutral-400 mt-2">
          将客户晒单、持续好评、创作者推广和集中差评作为独立冲击进入动态扩散，而不是把点赞量直接换算为销量。
        </p>
      </div>
      <Card>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#17243a" />
              <XAxis dataKey="period" tick={{ fill: "#8793a8", fontSize: 10 }} label={{ value: "模拟周期", position: "bottom", fill: "#8793a8", fontSize: 11 }} />
              <YAxis tick={{ fill: "#8793a8", fontSize: 10 }} domain={["auto", "auto"]} tickFormatter={value => `${Math.round(Number(value))}`} />
              <Tooltip contentStyle={{ background: "#091120", border: "1px solid #213456", borderRadius: 8, fontSize: 11 }} formatter={value => [`${Number(value).toFixed(1)}`, "相对销售指数"]} />
              <Legend />
              {scenarios.map(([id, name]) => (
                <Line key={id} type="monotone" dataKey={id} name={name} stroke={SOCIAL_COLORS[id] ?? "#ffffff"} strokeWidth={id === "baseline" ? 2 : 2.4} dot={{ r: 2 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="text-[10px] text-neutral-500 mt-3">基准自然传播 = 100。当前系数是可替换传播先验，尚未由真实平台曝光—互动—成交链路校准。</p>
      </Card>
      <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {finalPoints.map(item => (
          <Card key={item.scenario_id}>
            <span className="eyebrow">{item.name}</span>
            <div className="text-2xl font-semibold mt-2" style={{ color: SOCIAL_COLORS[item.scenario_id] }}>
              {item.relative_sales_index.toFixed(1)}
            </div>
            <div className="text-[10px] text-neutral-500 mt-1">
              期末相对销售指数 · 情绪平衡 {item.sentiment_balance > 0 ? "+" : ""}{item.sentiment_balance}
            </div>
          </Card>
        ))}
      </div>
      <Card className="border-amber-300/20">
        <div className="flex gap-3">
          <AlertTriangle size={17} className="text-amber-200 shrink-0 mt-0.5" />
          <p className="text-xs leading-relaxed text-neutral-400">
            真正接入社交网络后，应使用可验证的曝光、播放、互动、分享、情绪、评价星级、时间衰减和归因成交数据重新估计这些参数；单条爆款或高互动不等于增量销售。
          </p>
        </div>
      </Card>
      {data.social_evidence && (
        <div>
          <div className="flex items-end justify-between gap-3 mb-3">
            <div>
              <div className="eyebrow">平台数据获取条件</div>
              <h3 className="text-sm font-semibold text-white mt-1">社交与电商数据接入状态</h3>
            </div>
            <span className="text-[10px] text-neutral-500 font-mono">{data.social_evidence.version}</span>
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            {data.social_evidence.platforms.map(platform => (
              <Card key={platform.platform}>
                <div className="flex justify-between gap-3">
                  <strong className="text-xs text-white">{platform.platform}</strong>
                  <span className="text-[9px] text-blue-200 bg-blue-400/10 px-2 py-1 rounded-full h-fit">{statusLabel(platform.status)}</span>
                </div>
                <p className="text-[11px] text-neutral-400 leading-relaxed mt-3">{platform.recommended_path}</p>
                <p className="text-[10px] text-neutral-500 mt-2">
                  公开数据限制：{PLATFORM_ACCESS_LABELS[platform.public_market_scan] ?? platform.public_market_scan}
                </p>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MarketIntelligenceSection({ data }: { data: ReportData }) {
  const research = data.market_research;
  const platformEntries = Object.entries(research?.platform_counts ?? {});
  const consumerSearchSources = research?.evidence?.filter(
    item => item.source_type === "consumer_public_search",
  ) ?? [];
  const firecrawlCollector = research?.collectors?.find(
    item => item.collector === "Firecrawl multi-query consumer research",
  );
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">AI 市场情报扫描</div>
        <h2 className="text-base font-semibold text-white tracking-tight">公开资料、来源与可信度</h2>
        <p className="text-xs text-neutral-400 mt-2 max-w-3xl leading-relaxed">
          所有研究都由 Google Cloud 后台完成，客户不需要授权社交或电商账号。
          系统只读取允许公开访问的资料，并保存来源、采集时间和内容指纹；
          登录页、验证码和非公开经营数据不会进入报告。
        </p>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <Card>
          <div className="eyebrow">采集状态</div>
          <div className="text-lg text-white mt-2">{statusLabel(research?.status ?? "not_used")}</div>
        </Card>
        <Card>
          <div className="eyebrow">可追溯来源</div>
          <div className="text-lg text-white mt-2">{research?.source_count ?? 0} 条</div>
          <div className="text-[10px] text-neutral-500 mt-1">
            候选 {research?.candidate_count ?? research?.source_count ?? 0} 条
          </div>
        </Card>
        <Card>
          <div className="eyebrow">消费者公开检索</div>
          <div className="text-lg text-white mt-2">{consumerSearchSources.length} 条</div>
          <div className="text-[10px] text-neutral-500 mt-1">
            {statusLabel(firecrawlCollector?.status ?? "not_used")}
          </div>
        </Card>
        <Card>
          <div className="eyebrow">研究版本</div>
          <div className="text-[11px] text-neutral-300 font-mono mt-2 break-all">
            {research?.version ?? "未执行"}
          </div>
        </Card>
      </div>

      {!!platformEntries.length && (
        <div className="flex flex-wrap gap-2">
          {platformEntries.map(([platform, count]) => (
            <span key={platform} className="text-[10px] px-2.5 py-1 rounded-full bg-blue-400/10 text-blue-100">
              {platform} · {count}
            </span>
          ))}
        </div>
      )}

      {firecrawlCollector && firecrawlCollector.status !== "disabled" && (
        <Card className="border-cyan-300/20">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="eyebrow">像消费者一样公开检索</div>
              <p className="text-xs text-neutral-300 mt-2 leading-relaxed">
                系统会围绕价格、优缺点、真实使用、负面评价、竞品、售后和购买场景执行
                {firecrawlCollector.query_count ?? research?.consumer_search_queries?.length ?? 0} 组泰文检索。
                本次获得 {firecrawlCollector.result_count} 条通过质量检查的结果。
              </p>
            </div>
            <span className="text-[9px] text-cyan-100 bg-cyan-400/10 px-2 py-1 rounded-full whitespace-nowrap">
              约 {firecrawlCollector.estimated_credits ?? 0} 检索额度
            </span>
          </div>
          {!!research?.consumer_search_queries?.length && (
            <p className="text-[10px] text-neutral-500 mt-3 break-words">
              已完成 {firecrawlCollector.completed_queries ?? 0} 组主题；
              有效证据目标 {research.evidence_target?.minimum ?? 80}–
              {research.evidence_target?.maximum ?? 150} 条。
            </p>
          )}
          <p className="text-[10px] text-amber-100/70 mt-2">
            公开搜索摘要只作为发现线索；登录页、验证码和反爬页面不会进入证据，
            搜索结果也不会冒充平台成交数据。
          </p>
        </Card>
      )}

      {!research?.evidence?.length ? (
        <Card className="border-amber-300/20">
          <div className="flex gap-3">
            <AlertTriangle size={17} className="text-amber-200 shrink-0 mt-0.5" />
            <p className="text-xs text-neutral-400 leading-relaxed">
              本次没有取得可展示的公开网络资料。模拟仍使用已披露的官方宏观数据与模型先验，
              不会伪造网页、评论或平台成交数据。
            </p>
          </div>
        </Card>
      ) : (
        <div className="grid md:grid-cols-2 gap-3">
          {research.evidence.map(item => (
            <Card key={item.source_id}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-wrap gap-1.5">
                  <span className="text-[10px] text-blue-100 bg-blue-400/10 px-2 py-1 rounded-full">
                    {item.platform}
                  </span>
                  <span className="text-[10px] text-cyan-100 bg-cyan-400/10 px-2 py-1 rounded-full">
                    {SOURCE_TYPE_LABELS[item.source_type] ?? item.source_type}
                  </span>
                </div>
                <span className="text-[10px] text-neutral-500">证据等级 {item.evidence_grade}</span>
              </div>
              <a
                href={item.url}
                target="_blank"
                rel="noreferrer"
                className="block text-sm text-white font-medium mt-3 hover:underline"
              >
                {item.title}
              </a>
              {item.excerpt && (
                <p className="text-[11px] text-neutral-400 mt-2 leading-relaxed line-clamp-4">
                  {item.excerpt}
                </p>
              )}
              <div className="text-[9px] text-neutral-600 font-mono mt-3 break-all">
                {COLLECTOR_LABELS[item.collector] ?? item.collector} · {item.collected_at} · {item.content_sha256.slice(0, 16)}
              </div>
              {item.evidence_role && (
                <p className="text-[10px] text-neutral-500 mt-2">用途：{item.evidence_role}</p>
              )}
              <p className="text-[10px] text-amber-100/70 mt-2">局限：{item.limitation}</p>
            </Card>
          ))}
        </div>
      )}

      <Card>
        <div className="eyebrow">这些资料如何参与结论</div>
        <p className="text-xs text-neutral-300 mt-2 leading-relaxed">
          当前用于补充竞品、价格、评价主题、传播素材和风险问题；在没有客户订单、广告归因或
          A/B 测试完成校准前，公开互动量不会直接修改购买率。
        </p>
      </Card>
    </div>
  );
}

function ConsumerVoicesSection({ data }: { data: ReportData }) {
  const terms = reportTerms(data);
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">定性反馈与原因解释</div>
        <h2 className="text-base font-semibold text-white tracking-tight">消费者解释与模型细分</h2>
      </div>

      <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-900 flex items-start gap-3">
        <AlertTriangle size={15} className="text-neutral-500 shrink-0 mt-0.5" />
        <p className="text-xs text-neutral-300 font-light leading-relaxed">
          说明：大语言模型（LLM）可用时，这里展示代表样本的结构化辅助判断；不可用时展示选择模型的人群摘要。
          两者都不是真人访谈原话，也不会直接决定{terms.probability}。
        </p>
      </div>

      <div className="space-y-4">
        {data.consumer_voices.length === 0 && (
          <>
            <Card>
              <p className="text-xs text-neutral-400">
                本次没有可验证的大语言模型代表样本输出。以下内容来自选择模型的人群分群结果，仅用于解释主要驱动因素、
                阻碍和渠道偏好，不应当作真实消费者访谈原话。
              </p>
            </Card>
            {data.segments.slice(0, 5).map(segment => (
              <Card key={segment.segment_id ?? segment.name}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <strong className="text-sm text-white">{segment.name}</strong>
                  <span className="text-[10px] px-2 py-1 rounded-full bg-amber-300/10 text-amber-200">模型摘要 · 非消费者原话</span>
                </div>
                <p className="text-xs text-neutral-300 mt-3">
                  主要驱动：{segment.drivers.join("、") || "未识别"}；主要阻碍：{segment.barriers.join("、") || "未识别"}。
                </p>
                <p className="text-[10px] text-neutral-500 mt-2">
                  模型选择概率 {formatPercent(segment.purchase_rate)} · 偏好渠道 {segment.preferred_channel || "尚未识别"}
                </p>
              </Card>
            ))}
          </>
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
    name: ATTRIBUTE_LABELS[item.attribute] ?? item.attribute,
    impact: Math.min(1, Math.abs(item.implied_wtp_thb) / Math.max(1, midpoint?.price ?? 1)),
    desc: `属性评分提高 ${item.score_increase.toFixed(1)} 时，模型推算的先验边际支付意愿约为 ฿${item.implied_wtp_thb.toFixed(2)}`,
  }));
  if (midpoint && elasticity.length >= 3) {
    const lower = elasticity[Math.max(0, Math.floor(elasticity.length / 2) - 1)];
    params.unshift({
      name: "售价",
      impact: Math.min(1, Math.abs(lower.purchase_rate - midpoint.purchase_rate) / Math.max(0.01, midpoint.purchase_rate)),
      desc: `售价从 ฿${midpoint.price} 降至 ฿${lower.price} 时，模型购买概率由 ${formatPercent(midpoint.purchase_rate)} 变为 ${formatPercent(lower.purchase_rate)}`,
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">结果敏感性</div>
        <h2 className="text-base font-semibold text-white tracking-tight">关键参数敏感性说明</h2>
      </div>

      <Card>
        <div className="space-y-4">
          {params.length === 0 && (
            <p className="text-xs text-neutral-400">本套餐未生成敏感性或支付意愿（WTP）结果。</p>
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
  const decisionJourney = data.model_lineage?.decision_journey;
  const category = data.model_lineage?.category;
  return (
    <div className="space-y-6">
      <div>
        <div className="eyebrow mb-1">方法与数据来源</div>
        <h2 className="text-base font-semibold text-white tracking-tight">数据血缘与方法附录</h2>
      </div>

      <Card>
        <div className="space-y-4 text-xs text-neutral-300 font-light leading-relaxed">
          <p>
            <strong className="text-white font-semibold">1. 人口数据校准：</strong>{" "}
            {calibrationLabel(calibration?.status ?? data.calibration_status)}。
            {calibrationClaim(calibration?.status ?? data.calibration_status, calibration?.claim)}
          </p>
          <p>
            <strong className="text-white font-semibold">2. 消费者选择模型：</strong>{" "}
            {MODEL_LABELS[data.model_lineage?.model_family ?? ""] ?? data.model_lineage?.model_family ?? "未记录"}。
            模型要求消费者在本项目方案、竞品和“不购买 / 不到店”之间进行选择；大语言模型的回答不会被直接平均成市场规模。
          </p>
          <p>
            <strong className="text-white font-semibold">3. 多阶段消费决策：</strong>{" "}
            本次使用 {decisionJourney?.consumer_parameter_count ?? "未记录"} 项消费者参数和{" "}
            {decisionJourney?.advanced_choice_parameter_count ?? "未记录"} 项选择参数，依次模拟
            {(decisionJourney?.stages ?? []).map(stage => funnelCopy(data, stage).label).join("、") || "基础选择流程"}。
          </p>
          <p>
            <strong className="text-white font-semibold">4. 结果区间与不确定性：</strong>{" "}
            {UNCERTAINTY_LABELS[uncertainty?.interval_type ?? ""] ?? uncertainty?.interval_type ?? "未记录"}。
            当前纳入：
            {(uncertainty?.components ?? []).map(component => UNCERTAINTY_LABELS[component] ?? component).join("；") || "未记录"}。
            历史回测误差：{uncertainty?.validated_forecast_error ?? "尚未建立，因此区间不是经过验证的销量置信区间"}。
          </p>
          <p>
            <strong className="text-white font-semibold">5. 大语言模型辅助信号：</strong>{" "}
            本次状态为“{statusLabel(agentSignal?.status ?? "not_used")}”，定量结果中的有效权重为 {formatPercent(agentSignal?.effective_weight ?? 0)}，
            完成代表样本 {agentSignal?.sample_size ?? 0} 个。不可用时系统不会用固定虚拟人物冒充真实研究结果。
          </p>
          <p>
            <strong className="text-white font-semibold">6. 品类目标人群：</strong>{" "}
            {CATEGORY_LABELS[category?.category_key ?? data.category_key ?? ""] ?? category?.category_key ?? data.category_key ?? "通用消费品"}；
            占全部 AI 模拟消费人群 {formatPercent(category?.eligible_population_share ?? 1)}。
            筛选依据：{eligibilityLabel(category?.eligibility_status)}。
          </p>
          <p>
            <strong className="text-white font-semibold">7. 数据追溯：</strong>{" "}
            已记录 {(calibration?.sources ?? []).filter(source => source.observed).length} 个真实观测数据源；
            本报告运行编号为 <code className="text-white font-mono bg-neutral-900 px-1 py-0.5 rounded">{data.run_id}</code>，
            可用于追查数据版本、模型版本和运行条件。
          </p>
          {(data.warnings || []).map((warning, index) => (
            <div key={index} className="p-3 rounded-lg bg-black/40 border border-neutral-900">
              <p className="text-neutral-300">
                <strong className="text-white">限制 {index + 1}：</strong>{warningLabel(warning)}
              </p>
              <span className="inline-block mt-2 text-[10px] px-2 py-0.5 rounded-full bg-amber-300/10 text-amber-200">
                原因：{limitationReason(warning)}
              </span>
            </div>
          ))}
        </div>
      </Card>
      <div>
        <div className="eyebrow mb-1">证据有限时的保守估计</div>
        <h3 className="text-sm font-semibold text-white">证据不足时仍保留的保守结果</h3>
        <p className="text-xs text-neutral-400 mt-2">
          当公开采集、官方接口或大语言模型不可用时，系统不会要求客户提供账号，也不会用伪造数据填空，而是保留可追溯的保守模型估计，
          并同时说明证据等级、计算依据和使用边界。
        </p>
      </div>
      <div className="grid md:grid-cols-2 gap-3">
        {(data.evidence_estimates || []).map(item => (
          <Card key={item.topic}>
            <div className="flex items-center justify-between gap-3">
              <strong className="text-xs text-white">{item.topic}</strong>
              <span className={cn(
                "text-[10px] px-2 py-1 rounded-full",
                item.grade === "B" ? "bg-emerald-400/10 text-emerald-200" :
                item.grade === "C" ? "bg-blue-400/10 text-blue-200" :
                "bg-amber-300/10 text-amber-200"
              )}>证据等级 {item.grade}</span>
            </div>
            <p className="text-sm text-white mt-3">{item.result}</p>
            <p className="text-[10px] text-neutral-500 mt-2">
              依据：{EVIDENCE_BASIS_LABELS[item.basis] ?? item.basis}
            </p>
            <p className="text-[10px] text-amber-100/70 mt-1">局限：{item.limitation}</p>
          </Card>
        ))}
      </div>
      <p className="text-[10px] text-neutral-500 leading-relaxed">
        证据等级说明：B 级表示有可追溯的公开统计或市场证据，但不等于真实成交数据；C 级表示人口结构已有校准，
        核心行为系数仍待验证；D 级表示主要用于方向判断和压力测试的已披露模型先验。
      </p>
      {!!data.evidence_acquisition?.collectors?.length && (
        <>
          <div>
            <div className="eyebrow mb-1">证据采集状态</div>
            <h3 className="text-sm font-semibold text-white">独立证据采集与降级状态</h3>
            <p className="text-xs text-neutral-400 mt-2">
              各采集器独立执行；单个平台失败不会阻断整份报告，系统会记录降级结果。
            </p>
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            {data.evidence_acquisition.collectors.map(item => (
              <Card key={item.collector}>
                <div className="flex items-start justify-between gap-3">
                  <strong className="text-xs text-white">{COLLECTOR_LABELS[item.collector] ?? item.collector}</strong>
                  <span className={cn(
                    "text-[10px] px-2 py-1 rounded-full shrink-0",
                    item.status === "succeeded"
                      ? "bg-emerald-400/10 text-emerald-200"
                      : item.status === "not_applicable"
                        ? "bg-neutral-700/50 text-neutral-300"
                        : "bg-amber-300/10 text-amber-200"
                  )}>
                    {statusLabel(item.status)}
                  </span>
                </div>
                <p className="text-[10px] text-neutral-500 mt-3">
                  已取得 {item.result_count} 条记录
                  {item.fallback_result ? `；数据不足时采用“${FALLBACK_LABELS[item.fallback_result] ?? item.fallback_result}”作为保守替代` : ""}
                </p>
              </Card>
            ))}
          </div>
        </>
      )}
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
