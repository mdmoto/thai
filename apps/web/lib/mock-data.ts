// Mock data for frontend development
// Replace with real API calls when backend is ready

export interface Study {
  id: string;
  name: string;
  study_type: string;
  status: string;
  plan_code: string;
  created_at: string;
  updated_at: string;
  organization_id: string;
}

export interface Organization {
  id: string;
  name: string;
  credits_balance: number;
  plan_code: string;
}

export const MOCK_ORG: Organization = {
  id: "org_demo_001",
  name: "示例企业",
  credits_balance: 24,
  plan_code: "PROFESSIONAL",
};

export const MOCK_STUDIES: Study[] = [
  {
    id: "study_001",
    name: "清迈 BKK 品牌宠物零食泰国市场测试",
    study_type: "PRODUCT_VALIDATION",
    status: "COMPLETED",
    plan_code: "PROFESSIONAL",
    created_at: "2026-07-20T10:00:00Z",
    updated_at: "2026-07-20T11:30:00Z",
    organization_id: "org_demo_001",
  },
  {
    id: "study_002",
    name: "Nimman Road 咖啡馆选址与经营方案",
    study_type: "CAFE",
    status: "RUNNING_SIMULATION",
    plan_code: "PROFESSIONAL",
    created_at: "2026-07-22T14:00:00Z",
    updated_at: "2026-07-22T14:45:00Z",
    organization_id: "org_demo_001",
  },
  {
    id: "study_003",
    name: "蓝牙耳机 Pro 定价测试 — THB 1,490 vs 1,890 vs 2,290",
    study_type: "PRICING_STUDY",
    status: "NEEDS_CONFIRMATION",
    plan_code: "STANDARD",
    created_at: "2026-07-23T09:00:00Z",
    updated_at: "2026-07-23T09:15:00Z",
    organization_id: "org_demo_001",
  },
  {
    id: "study_004",
    name: "Thonglor 鸡尾酒吧 Happy Hour 方案测试",
    study_type: "BAR",
    status: "COMPLETED",
    plan_code: "DEEP",
    created_at: "2026-07-18T16:00:00Z",
    updated_at: "2026-07-18T17:20:00Z",
    organization_id: "org_demo_001",
  },
  {
    id: "study_005",
    name: "智能宠物喂食器广告 A/B 测试",
    study_type: "CREATIVE_TEST",
    status: "DRAFT",
    plan_code: "STANDARD",
    created_at: "2026-07-23T17:00:00Z",
    updated_at: "2026-07-23T17:00:00Z",
    organization_id: "org_demo_001",
  },
];

export const MOCK_USAGE = [
  { date: "07-17", runs: 2, cost_usd: 8.3 },
  { date: "07-18", runs: 1, cost_usd: 4.1 },
  { date: "07-19", runs: 0, cost_usd: 0 },
  { date: "07-20", runs: 3, cost_usd: 12.4 },
  { date: "07-21", runs: 1, cost_usd: 3.9 },
  { date: "07-22", runs: 2, cost_usd: 9.2 },
  { date: "07-23", runs: 1, cost_usd: 4.5 },
];

// Study type metadata
export const STUDY_TYPE_META: Record<string, {
  label: string;
  desc: string;
  icon: string;
  inputs: string[];
  outputs: string[];
  color: string;
}> = {
  PRODUCT_VALIDATION: {
    label: "产品验证",
    desc: "测试新产品在泰国消费者中的购买意向、价格接受度和改进建议",
    icon: "📦",
    inputs: ["产品名称", "价格", "图片", "卖点", "竞品"],
    outputs: ["购买意向", "价格接受度", "人群画像", "改进建议"],
    color: "#D4A853",
  },
  VENUE_STUDY: {
    label: "门店研究",
    desc: "评估线下门店的客流、容量利用率和复购潜力",
    icon: "🏪",
    inputs: ["门店类型", "位置", "营业时间", "容量", "菜单/服务"],
    outputs: ["分时客流", "到店概率", "容量利用", "复购率"],
    color: "#2F9E74",
  },
  SITE_COMPARISON: {
    label: "选址对比",
    desc: "同时比较多个候选地址的商圈潜力和竞争环境",
    icon: "📍",
    inputs: ["2-10个候选地址"],
    outputs: ["人群覆盖", "距离阻力", "竞争强度", "相对排名"],
    color: "#2F9E74",
  },
  PRICING_STUDY: {
    label: "定价测试",
    desc: "比较不同价格方案对转化率、收入和利润的影响",
    icon: "💰",
    inputs: ["产品信息", "多个价格/套餐"],
    outputs: ["转化率对比", "收入预测", "最优定价建议"],
    color: "#D4A853",
  },
  CREATIVE_TEST: {
    label: "广告测试",
    desc: "测试广告素材的理解度、相关性和点击倾向",
    icon: "🎯",
    inputs: ["广告图/文案/视频脚本"],
    outputs: ["理解度", "相关性", "点击倾向", "渠道适配度"],
    color: "#B8503D",
  },
  OPERATING_SCENARIO: {
    label: "经营方案",
    desc: "模拟不同经营参数组合对客流和收入的影响",
    icon: "⚙️",
    inputs: ["营业时间", "座位数", "活动方案", "菜单/外卖"],
    outputs: ["客流预测", "容量利用", "收入区间", "运营风险"],
    color: "#2F9E74",
  },
  RESTAURANT: {
    label: "餐厅评估",
    desc: "深度评估餐厅各时段客流、翻台率和菜单接受度",
    icon: "🍜",
    inputs: ["菜系", "菜单", "客单价", "座位数", "配送"],
    outputs: ["各时段客流", "翻台率", "外卖占比", "复购率"],
    color: "#D4A853",
  },
  CAFE: {
    label: "咖啡馆评估",
    desc: "分析咖啡馆的目标客群、停留时长和座位利用率",
    icon: "☕",
    inputs: ["位置", "座位数", "WiFi/电源", "价格", "风格"],
    outputs: ["目标人群", "峰值客流", "停留时长", "回头率"],
    color: "#B8503D",
  },
  BAR: {
    label: "酒吧评估",
    desc: "评估酒吧的夜间客流、活动效果和Happy Hour策略",
    icon: "🍺",
    inputs: ["位置", "容量", "酒水单", "活动计划"],
    outputs: ["分时客流", "高峰容量", "活动增量", "带朋友率"],
    color: "#B8503D",
  },
  RETAIL: {
    label: "零售门店",
    desc: "评估实体零售店的选址、客单价和竞争环境",
    icon: "🛍️",
    inputs: ["商品品类", "位置", "定价", "装修风格"],
    outputs: ["客流预测", "转化率", "客单价", "竞争分析"],
    color: "#2F9E74",
  },
};

// Template library
export const TEMPLATES = [
  {
    id: "tpl_new_product",
    key: "new_product",
    study_type: "PRODUCT_VALIDATION",
    icon: "📦",
    recommended_plan: "PROFESSIONAL",
    scenarios: 3,
    est_time: "15-30 分钟",
  },
  {
    id: "tpl_ecommerce",
    key: "ecommerce",
    study_type: "PRODUCT_VALIDATION",
    icon: "🛒",
    recommended_plan: "STANDARD",
    scenarios: 2,
    est_time: "10-20 分钟",
  },
  {
    id: "tpl_restaurant",
    key: "restaurant",
    study_type: "RESTAURANT",
    icon: "🍜",
    recommended_plan: "PROFESSIONAL",
    scenarios: 4,
    est_time: "20-35 分钟",
  },
  {
    id: "tpl_bar",
    key: "bar",
    study_type: "BAR",
    icon: "🍺",
    recommended_plan: "PROFESSIONAL",
    scenarios: 3,
    est_time: "20-30 分钟",
  },
  {
    id: "tpl_cafe",
    key: "cafe",
    study_type: "CAFE",
    icon: "☕",
    recommended_plan: "STANDARD",
    scenarios: 2,
    est_time: "15-25 分钟",
  },
  {
    id: "tpl_ab_test",
    key: "ab_test",
    study_type: "CREATIVE_TEST",
    icon: "🎯",
    recommended_plan: "STANDARD",
    scenarios: 2,
    est_time: "10-15 分钟",
  },
  {
    id: "tpl_pricing",
    key: "pricing",
    study_type: "PRICING_STUDY",
    icon: "💰",
    recommended_plan: "PROFESSIONAL",
    scenarios: 3,
    est_time: "15-25 分钟",
  },
  {
    id: "tpl_site",
    key: "site",
    study_type: "SITE_COMPARISON",
    icon: "📍",
    recommended_plan: "PROFESSIONAL",
    scenarios: 5,
    est_time: "20-35 分钟",
  },
];

// Plan metadata
export const PLAN_META = {
  PREVIEW: {
    label: "预览版",
    population: 100,
    mc_rounds: 5,
    scenarios: 1,
    competitors: 1,
    geo: "城市",
    credits: 1,
    price_thb: 0,
    desc: "检查输入方向，不用于正式决策",
    features: ["方向性结果", "基础分析"],
    color: "#4A6280",
  },
  STANDARD: {
    label: "标准版",
    population: 10000,
    mc_rounds: 30,
    scenarios: 2,
    competitors: 2,
    geo: "城市",
    credits: 3,
    price_thb: 2900,
    desc: "单方案快速验证，基础报告",
    features: ["基础分群", "核心报告", "2个情景"],
    color: "#38BDF8",
  },
  PROFESSIONAL: {
    label: "专业版",
    population: 30000,
    mc_rounds: 50,
    scenarios: 4,
    competitors: 3,
    geo: "商圈",
    credits: 8,
    price_thb: 7900,
    desc: "方案比较，细分人群，多情景（主力产品）",
    features: ["细分人群", "4个情景", "敏感性分析", "数据导出"],
    color: "#D4A853",
    popular: true,
  },
  DEEP: {
    label: "深度版",
    population: 100000,
    mc_rounds: 80,
    scenarios: 6,
    competitors: 5,
    geo: "POI",
    credits: 20,
    price_thb: 19900,
    desc: "重要商业决策，多轮稳定性分析",
    features: ["高精度分层", "6个情景", "完整敏感性", "PDF报告", "优先支持"],
    color: "#8B5CF6",
  },
  ENTERPRISE: {
    label: "企业版",
    population: 300000,
    mc_rounds: 100,
    scenarios: 10,
    competitors: 10,
    geo: "全覆盖",
    credits: 60,
    price_thb: 0,
    desc: "大型项目与多区域，企业定制",
    features: ["30万人口", "专属支持", "白标报告", "API访问", "定制人群"],
    color: "#10B981",
  },
};
