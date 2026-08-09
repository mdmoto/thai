"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Building2,
  Check,
  Cpu,
  Database,
  GitCompareArrows,
  Globe,
  ShieldCheck,
} from "lucide-react";
import { BrandMark } from "@/components/brand-mark";
import { STUDY_TYPE_META } from "@/lib/product-catalog";

const SALES_URL =
  process.env.NEXT_PUBLIC_SALES_URL || "https://wa.me/66623458238";

const WORKFLOW = [
  {
    icon: Database,
    title: "一键录入商业方案",
    text: "填入您的新品卖点、预设定价或选址方案，系统自动匹配全泰宏观人口画像与最新竞品数据。",
  },
  {
    icon: GitCompareArrows,
    title: "启动人群模拟对抗演练",
    text: "基于离散选择算法，推演数万名仿真消费者在面对降价、品质差异及竞品夹击时的真实选择。",
  },
  {
    icon: BarChart3,
    title: "导出降维打击评估报告",
    text: "实时掌控受众穿透率、价格弹性黄金交叉点及经营死角，在同行盲目摸黑时抢占先机。",
  },
];

export default function HomePage() {
  const [isFlipped, setIsFlipped] = useState(false);

  return (
    <div
      className="relative w-full min-h-screen bg-black overflow-x-hidden"
      style={{ perspective: "2400px" }}
    >
      <motion.div
        animate={{ rotateY: isFlipped ? 180 : 0 }}
        transition={{ duration: 0.85, ease: [0.4, 0, 0.2, 1] }}
        style={{ transformStyle: "preserve-3d" }}
        className="relative w-full min-h-screen"
      >
        {/* 正面（0°）：当前 AI 决策商业沙盘主站 */}
        <div
          style={{ backfaceVisibility: "hidden" }}
          className={`w-full min-h-screen flex flex-col bg-base ${
            isFlipped ? "pointer-events-none select-none invisible" : ""
          }`}
        >
          <header className="max-w-7xl mx-auto px-5 sm:px-8 h-20 w-full flex items-center justify-between border-b border-blue-400/10">
            <Link href="/" className="flex items-center">
              <BrandMark full className="w-32 sm:w-52 h-auto" priority />
            </Link>
            <nav className="flex items-center gap-2 sm:gap-3">
              <button
                type="button"
                onClick={() => setIsFlipped(true)}
                className="px-3.5 py-1.5 rounded-full bg-white/[0.08] hover:bg-white/[0.16] border border-white/20 text-neutral-200 hover:text-white text-xs sm:text-[13px] font-medium transition-all duration-300 backdrop-blur-md flex items-center gap-1.5 shadow-sm"
              >
                <span>清迈 AI 中心官网</span>
                <ArrowUpRight className="w-3.5 h-3.5 opacity-70" />
              </button>
              <div className="hidden md:block">
                <Link href="/methodology" className="btn-cmai-ghost">
                  方法与数据
                </Link>
              </div>
              <Link href="/login" className="btn-cmai-secondary">
                登录
              </Link>
              <Link
                href="/studies/new?type=PRODUCT_VALIDATION"
                className="btn-cmai-primary"
              >
                开始测试
              </Link>
            </nav>
          </header>

          <main className="flex-grow">
            <section className="hero-grid max-w-7xl mx-auto px-5 sm:px-8 pt-16 sm:pt-24 pb-20">
              <div className="max-w-4xl">
                <span className="eyebrow text-blue-300">
                  泰国出海商业沙盘系统
                </span>
                <h1 className="text-4xl sm:text-6xl font-semibold tracking-tight leading-[1.05] text-white mt-5">
                  在资本投入前
                  <br />
                  完成 6.6 亿次真实消费推演
                </h1>
                <p className="text-base sm:text-lg text-neutral-400 leading-relaxed max-w-2xl mt-6">
                  从曼谷核心商圈选址，到 Shopee/TikTok 爆品定价。30 万 AI 数字消费者在正式上线前，为你还原真实的市场博弈与转化全貌。
                </p>
                <div className="flex flex-wrap gap-3 mt-8">
                  <Link href="/demo/pet-water" className="btn-cmai-primary">
                    免费体验：查看宠物饮水机沙盘报告 <ArrowRight size={14} />
                  </Link>
                  <Link href="/methodology" className="btn-cmai-secondary">
                    查看决策模型原理
                  </Link>
                </div>
                <div className="flex flex-wrap gap-x-6 gap-y-2 mt-8 text-xs text-neutral-500">
                  <span className="flex items-center gap-1.5">
                    <Check size={13} /> 全泰 77 府真实宏观人口结构建模
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Check size={13} /> 真实推演“买你 / 买竞品 / 放弃购买”
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Check size={13} /> 剔除主观偏见，离散选择数学校验
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Check size={13} /> 生成可沉淀、可回溯的企业级商业报告
                  </span>
                </div>
              </div>
            </section>

            <section className="border-y border-neutral-900 bg-[#0d0d0d]">
              <div className="max-w-7xl mx-auto px-5 sm:px-8 py-12 grid grid-cols-2 lg:grid-cols-4 gap-6">
                <Metric
                  value="77 府"
                  label="泰国全境人口分布与消费画像深度覆盖"
                />
                <Metric
                  value="30万+"
                  label="数字化高仿真消费者在线对抗演练"
                />
                <Metric
                  value="0 试错成本"
                  label="落地前提前预判价格弹性与亏损陷阱"
                />
                <Metric
                  value="5 分钟"
                  label="快速交付企业级数据决策报告"
                />
              </div>
            </section>

            <section className="max-w-7xl mx-auto px-5 sm:px-8 py-20">
              <div className="max-w-2xl mb-10">
                <span className="eyebrow">使用流程</span>
                <h2 className="text-3xl font-semibold text-white mt-3">
                  只需 3 步，像玩兵棋推演一样做泰国商业决策
                </h2>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {WORKFLOW.map((item, index) => (
                  <div key={item.title} className="cmai-card p-6">
                    <div className="flex items-center justify-between">
                      <item.icon size={20} className="text-neutral-300" />
                      <span className="text-xs font-mono text-neutral-600">
                        0{index + 1}
                      </span>
                    </div>
                    <h3 className="text-base font-semibold text-white mt-8">
                      {item.title}
                    </h3>
                    <p className="text-sm text-neutral-400 leading-relaxed mt-2">
                      {item.text}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            <section className="max-w-7xl mx-auto px-5 sm:px-8 pb-20">
              <div className="max-w-2xl mb-10">
                <span className="eyebrow">研究类型</span>
                <h2 className="text-3xl font-semibold text-white mt-3">
                  覆盖出海全生命周期：6 大高精准度商业决策场景
                </h2>
                <p className="text-sm text-neutral-400 mt-3">
                  针对不同业态深度建模，精准评估到店率、转化率与客单价，绝不做泛泛而谈的粗暴预测。
                </p>
              </div>
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(STUDY_TYPE_META).map(([key, item]) => (
                  <Link
                    key={key}
                    href={`/studies/new?type=${key}`}
                    className="cmai-card p-5 group"
                  >
                    <div className="flex items-start justify-between">
                      <span className="text-2xl">{item.icon}</span>
                      <ArrowRight
                        size={15}
                        className="text-neutral-600 group-hover:text-blue-300 transition-colors"
                      />
                    </div>
                    <h3 className="text-sm font-semibold text-white mt-5">
                      {item.label}
                    </h3>
                    <p className="text-xs text-neutral-400 leading-relaxed mt-2">
                      {item.desc}
                    </p>
                  </Link>
                ))}
              </div>
            </section>

            <section className="max-w-7xl mx-auto px-5 sm:px-8 pb-20">
              <div className="cmai-card p-7 sm:p-10 grid grid-cols-1 lg:grid-cols-2 gap-10">
                <div>
                  <ShieldCheck size={24} className="text-neutral-300" />
                  <h2 className="text-2xl font-semibold text-white mt-5">
                    多维数据穿透，为每一项商业决策保驾护航
                  </h2>
                  <p className="text-sm text-neutral-400 leading-relaxed mt-3">
                    结合全泰宏观经济统计与离散选择算法，为您深度剖析新品受众、竞品壁垒与价格敏感度，
                    帮您在真实大预算投入前清障排毒。
                  </p>
                </div>
                <div className="space-y-3 text-sm text-neutral-300">
                  {[
                    "人口与收入：精准同步泰国国家统计局（NSO）宏观微观数据",
                    "消费者选择：真实推演“买你 / 买竞品 / 放弃购买”博弈",
                    "算法深度校验：数学模型多重验证，剔除 LLM 虚假幻觉",
                    "竞品对比推演：基于实测报价与全网口碑，还原真实战场",
                  ].map(item => (
                    <div
                      key={item}
                      className="flex items-start gap-2 border-b border-neutral-900 pb-3"
                    >
                      <Check
                        size={14}
                        className="mt-0.5 text-emerald-400 shrink-0"
                      />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            <section className="border-y border-neutral-900 bg-[#0d0d0d]">
              <div className="max-w-7xl mx-auto px-5 sm:px-8 py-20">
                <div className="max-w-2xl mb-10">
                  <span className="eyebrow">套餐与价格</span>
                  <h2 className="text-3xl font-semibold text-white mt-3">
                    零门槛试错，到企业级深度商研决策
                  </h2>
                  <p className="text-sm text-neutral-400 mt-3">
                    基础模拟灵活支持积分即用；深度决策按次生成全面可行性分析。
                  </p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                  <PricingCard
                    name="免费预览"
                    price="免费"
                    note="每个账号 1 次"
                    items={[
                      "100 人 AI 模拟消费人群",
                      "快速预检方案与需求验证",
                      "快速生成基础测评视点",
                    ]}
                  />
                  <PricingCard
                    name="基础模拟"
                    price="5 积分"
                    note="有效邀请码可赠送一次"
                    items={[
                      "5,000 人 AI 模拟消费人群",
                      "快速比较价格、卖点和方案",
                      "适合日常小范围测试",
                    ]}
                  />
                  <PricingCard
                    name="基础决策"
                    price="฿990 / 次"
                    note="购买 1 次并赠送 1 积分"
                    items={[
                      "20,000 人 AI 模拟消费人群",
                      "进阶消费者决策模型",
                      "生成基础决策报告",
                    ]}
                  />
                  <PricingCard
                    name="深度决策"
                    price="฿7,900 / 次起"
                    note="单次专业决策包另赠 10 积分"
                    items={[
                      "300,000 人 AI 模拟消费人群",
                      "完整竞品、价格与风险分析",
                      "生成正式商业决策报告",
                    ]}
                    featured
                  />
                </div>
                <p className="text-[11px] text-neutral-500 mt-5">
                  所有价格以泰铢计；当前使用页面固定收款码，扫码后由人工核验到账再入账。企业数据校准与历史回测按项目另行签约，不属于当前自助套餐。
                </p>
              </div>
            </section>

            <section className="border-t border-neutral-900">
              <div className="max-w-7xl mx-auto px-5 sm:px-8 py-16 flex flex-col sm:flex-row sm:items-center justify-between gap-6">
                <div>
                  <span className="eyebrow">开始比较方案</span>
                  <h2 className="text-2xl font-semibold text-white mt-2">
                    创建第一个泰国消费品研究
                  </h2>
                </div>
                <Link href="/login" className="btn-cmai-primary">
                  注册并开始 <ArrowRight size={14} />
                </Link>
              </div>
            </section>
          </main>

          <footer className="border-t border-neutral-900">
            <div className="max-w-7xl mx-auto px-5 sm:px-8 py-8 flex flex-col sm:flex-row justify-between items-center gap-4 text-xs text-neutral-500">
              <div className="flex items-center gap-3">
                <span>Chiang Mai AI Center · Thailand</span>
                <span className="text-neutral-700">|</span>
                <button
                  type="button"
                  onClick={() => setIsFlipped(true)}
                  className="text-neutral-400 hover:text-white transition-colors flex items-center gap-1"
                >
                  <span>访问清迈实体枢纽</span>
                  <ArrowUpRight className="w-3 h-3" />
                </button>
              </div>
              <div className="flex gap-4">
                <Link href="/methodology">方法</Link>
                <Link href="/terms">条款</Link>
                <Link href="/privacy">隐私</Link>
                <a href={SALES_URL} target="_blank" rel="noopener noreferrer">
                  销售联系
                </a>
              </div>
            </div>
          </footer>
        </div>

        {/* 背面（180度翻转面）：清迈 AI 中心实体枢纽与官网主站 portal */}
        <div
          style={{
            backfaceVisibility: "hidden",
            transform: "rotateY(180deg)",
          }}
          className={`absolute inset-0 w-full min-h-screen bg-[#070b14] text-white flex flex-col justify-between overflow-y-auto ${
            !isFlipped ? "pointer-events-none select-none invisible" : ""
          }`}
        >
          {/* 背面顶部导航栏 */}
          <header className="max-w-7xl mx-auto px-5 sm:px-8 h-20 w-full flex items-center justify-between border-b border-white/10 shrink-0">
            <div className="flex items-center gap-3">
              <BrandMark full className="w-32 sm:w-52 h-auto" priority />
            </div>
            <button
              type="button"
              onClick={() => setIsFlipped(false)}
              className="px-4 py-1.5 rounded-full bg-white/[0.08] hover:bg-white/[0.16] border border-white/20 text-neutral-200 hover:text-white text-xs sm:text-[13px] font-medium transition-all duration-300 backdrop-blur-md flex items-center gap-1.5 shadow-sm"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>翻转返回沙盘系统</span>
            </button>
          </header>

          {/* 背面主体视觉与业务模块 */}
          <main className="flex-grow flex items-center justify-center py-12 px-5 sm:px-8">
            <div className="max-w-5xl w-full mx-auto space-y-12">
              <div className="text-center space-y-5 max-w-3xl mx-auto">
                <span className="eyebrow text-blue-400">
                  CHIANG MAI AI CENTER · 实体创新生态枢纽
                </span>
                <h1 className="text-3xl sm:text-5xl font-semibold tracking-tight text-white leading-tight">
                  清迈 AI 中心实体枢纽
                  <br />
                  <span className="text-neutral-400 text-2xl sm:text-4xl font-light">
                    连接全球创新技术与东南亚商业落地
                  </span>
                </h1>
                <p className="text-sm sm:text-base text-neutral-400 leading-relaxed max-w-2xl mx-auto">
                  立足泰北绿色低碳创新腹地，为面向东南亚及全球的科技企业、出海技术团队与数字化品牌提供实体研发空间、智算底座及全链条商业合规落地服务。
                </p>
              </div>

              {/* 三大核心基础设施能力卡片 */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                <div className="cmai-card p-6 sm:p-7 border-white/10 bg-white/[0.02] backdrop-blur-md flex flex-col justify-between">
                  <div>
                    <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 mb-5">
                      <Cpu size={20} />
                    </div>
                    <h3 className="text-base font-semibold text-white mb-2">
                      绿色智算底座
                    </h3>
                    <p className="text-xs text-neutral-400 leading-relaxed">
                      依托泰北丰富的水力清洁能源与分布式算力节点，为企业级仿真对抗推演、私有化模型微调及跨境数据处理提供低碳、高能效的算力支撑。
                    </p>
                  </div>
                  <div className="mt-6 pt-4 border-t border-white/5 text-[11px] text-neutral-500">
                    低延迟网络 · 边缘节点集群
                  </div>
                </div>

                <div className="cmai-card p-6 sm:p-7 border-white/10 bg-white/[0.02] backdrop-blur-md flex flex-col justify-between">
                  <div>
                    <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-5">
                      <Building2 size={20} />
                    </div>
                    <h3 className="text-base font-semibold text-white mb-2">
                      高规格研发与办公空间
                    </h3>
                    <p className="text-xs text-neutral-400 leading-relaxed">
                      位于清迈核心科技园区，提供独立品牌办公室、共享技术工位、千兆国际专线接入与国际化双语商务会议展示中心。
                    </p>
                  </div>
                  <div className="mt-6 pt-4 border-t border-white/5 text-[11px] text-neutral-500">
                    独立办公区 · 商务接待配套
                  </div>
                </div>

                <div className="cmai-card p-6 sm:p-7 border-white/10 bg-white/[0.02] backdrop-blur-md flex flex-col justify-between">
                  <div>
                    <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 mb-5">
                      <Globe size={20} />
                    </div>
                    <h3 className="text-base font-semibold text-white mb-2">
                      出海合规与全案加速
                    </h3>
                    <p className="text-xs text-neutral-400 leading-relaxed">
                      联合泰国投资促进委员会（BOI）及本土律所财税机构，提供泰国公司设立、工作签证办理、合规审查与东南亚商业伙伴精准对接。
                    </p>
                  </div>
                  <div className="mt-6 pt-4 border-t border-white/5 text-[11px] text-neutral-500">
                    BOI 政策咨询 · 跨境落地服务
                  </div>
                </div>
              </div>

              {/* 核心操作按钮组 */}
              <div className="flex flex-wrap items-center justify-center gap-3 sm:gap-4 pt-2">
                <button
                  type="button"
                  onClick={() => setIsFlipped(false)}
                  className="px-6 py-3 rounded-full bg-white/[0.08] hover:bg-white/[0.18] border border-white/20 text-white text-xs sm:text-sm font-medium transition-all backdrop-blur-md flex items-center gap-2 shadow-sm"
                >
                  <ArrowLeft className="w-4 h-4" />
                  <span>翻转返回沙盘系统</span>
                </button>

                <a
                  href="https://lazzor.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-6 py-3 rounded-full bg-white hover:bg-neutral-200 text-neutral-950 text-xs sm:text-sm font-semibold transition-all flex items-center gap-2 shadow-lg hover:shadow-white/10"
                >
                  <span>进入官网主站 (lazzor.com)</span>
                  <ArrowUpRight className="w-4 h-4" />
                </a>

                <a
                  href={SALES_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-6 py-3 rounded-full bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 text-blue-300 text-xs sm:text-sm font-medium transition-all backdrop-blur-md flex items-center gap-2"
                >
                  <span>空间入驻与商务咨询</span>
                  <ArrowUpRight className="w-4 h-4" />
                </a>
              </div>
            </div>
          </main>

          {/* 背面底部版权 */}
          <footer className="border-t border-white/10 shrink-0">
            <div className="max-w-7xl mx-auto px-5 sm:px-8 py-6 flex flex-col sm:flex-row justify-between items-center gap-4 text-xs text-neutral-500">
              <span>Chiang Mai AI Center · 泰国清迈创新中心</span>
              <div className="flex items-center gap-4">
                <a
                  href="https://lazzor.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-neutral-400 hover:text-white transition-colors flex items-center gap-1"
                >
                  <span>官网主站</span>
                  <ArrowUpRight className="w-3 h-3" />
                </a>
                <span className="text-neutral-700">|</span>
                <button
                  type="button"
                  onClick={() => setIsFlipped(false)}
                  className="text-neutral-400 hover:text-white transition-colors"
                >
                  商业沙盘
                </button>
                <span className="text-neutral-700">|</span>
                <a
                  href={SALES_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-neutral-400 hover:text-white transition-colors"
                >
                  销售联系
                </a>
              </div>
            </div>
          </footer>
        </div>
      </motion.div>
    </div>
  );
}

function Metric({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="text-2xl sm:text-3xl font-semibold text-white">
        {value}
      </div>
      <div className="text-xs text-neutral-500 mt-2">{label}</div>
    </div>
  );
}

function PricingCard({
  name,
  price,
  note,
  items,
  featured = false,
}: {
  name: string;
  price: string;
  note: string;
  items: string[];
  featured?: boolean;
}) {
  return (
    <div className={`cmai-card p-6 ${featured ? "border-neutral-600" : ""}`}>
      <span className="eyebrow">{name}</span>
      <div className="text-2xl font-semibold text-white mt-4">{price}</div>
      <p className="text-xs text-neutral-500 mt-1">{note}</p>
      <div className="space-y-2 mt-6">
        {items.map(item => (
          <div
            key={item}
            className="flex items-start gap-2 text-xs text-neutral-300"
          >
            <Check size={13} className="text-emerald-400 mt-0.5 shrink-0" />
            <span>{item}</span>
          </div>
        ))}
      </div>
      <Link
        href="/login"
        className={
          featured
            ? "btn-cmai-primary mt-7 w-full"
            : "btn-cmai-secondary mt-7 w-full"
        }
      >
        开始使用
      </Link>
    </div>
  );
}
