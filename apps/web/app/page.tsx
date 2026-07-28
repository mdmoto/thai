import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  Check,
  Database,
  GitCompareArrows,
  ShieldCheck,
} from "lucide-react";
import { BrandMark } from "@/components/brand-mark";
import { STUDY_TYPE_META } from "@/lib/product-catalog";

const SALES_URL =
  process.env.NEXT_PUBLIC_SALES_URL || "https://wa.me/66623458238";

const WORKFLOW = [
  {
    icon: Database,
    title: "确认市场与输入",
    text: "使用泰国官方宏观人口校准，记录产品、价格和竞品证据版本。",
  },
  {
    icon: GitCompareArrows,
    title: "比较选择情景",
    text: "通过离散选择模型比较基准、降价、品质、本地信任和传播方案。",
  },
  {
    icon: BarChart3,
    title: "读取可追溯报告",
    text: "查看目标人群、价格弹性、情景排序、假设和未验证限制。",
  },
];

export default function HomePage() {
  return (
    <main className="min-h-screen bg-base">
      <header className="max-w-7xl mx-auto px-5 sm:px-8 h-20 flex items-center justify-between border-b border-blue-400/10">
        <Link href="/" className="flex items-center">
          <BrandMark full className="w-32 sm:w-52 h-auto" priority />
        </Link>
        <nav className="flex items-center gap-2">
          <div className="hidden sm:block">
            <Link href="/methodology" className="btn-cmai-ghost">
              方法与数据
            </Link>
          </div>
          <Link href="/login" className="btn-cmai-secondary">登录</Link>
          <Link href="/studies/new?type=PRODUCT_VALIDATION" className="btn-cmai-primary">
            开始测试
          </Link>
        </nav>
      </header>

      <section className="hero-grid max-w-7xl mx-auto px-5 sm:px-8 pt-16 sm:pt-24 pb-20">
        <div className="max-w-4xl">
          <span className="eyebrow text-blue-300">泰国市场商业决策平台</span>
          <h1 className="text-4xl sm:text-6xl font-semibold tracking-tight leading-[1.05] text-white mt-5">
            进入泰国市场前，
            <br />
            先比较产品、价格与竞品情景
          </h1>
          <p className="text-base sm:text-lg text-neutral-400 leading-relaxed max-w-2xl mt-6">
            让 AI 模拟消费人群先替您试一遍。比较产品、价格、广告、选址和经营方案，
            再决定钱该花在哪里。
          </p>
          <div className="flex flex-wrap gap-3 mt-8">
            <Link href="/demo/pet-water" className="btn-cmai-primary">
              查看宠物饮水机完整报告 <ArrowRight size={14} />
            </Link>
            <Link href="/methodology" className="btn-cmai-secondary">
              查看可信度边界
            </Link>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-2 mt-8 text-xs text-neutral-500">
            <span className="flex items-center gap-1.5"><Check size={13} /> 泰国 77 府人口覆盖</span>
            <span className="flex items-center gap-1.5"><Check size={13} /> 竞品与不购买选项</span>
            <span className="flex items-center gap-1.5"><Check size={13} /> 不把大模型回答直接当作销量</span>
            <span className="flex items-center gap-1.5"><Check size={13} /> 报告记录假设和版本</span>
          </div>
        </div>
      </section>

      <section className="border-y border-neutral-900 bg-[#0d0d0d]">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-12 grid grid-cols-2 lg:grid-cols-4 gap-6">
          <Metric value="77" label="泰国府级人口覆盖" />
          <Metric value="15" label="首个品类公开报价" />
          <Metric value="30万" label="深度决策 AI 模拟消费人群" />
          <Metric value="多方案" label="价格、竞品与风险同时比较" />
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-5 sm:px-8 py-20">
        <div className="max-w-2xl mb-10">
          <span className="eyebrow">使用流程</span>
          <h2 className="text-3xl font-semibold text-white mt-3">从输入到决策，不隐藏模型边界</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {WORKFLOW.map((item, index) => (
            <div key={item.title} className="cmai-card p-6">
              <div className="flex items-center justify-between">
                <item.icon size={20} className="text-neutral-300" />
                <span className="text-xs font-mono text-neutral-600">0{index + 1}</span>
              </div>
              <h3 className="text-base font-semibold text-white mt-8">{item.title}</h3>
              <p className="text-sm text-neutral-400 leading-relaxed mt-2">{item.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-5 sm:px-8 pb-20">
        <div className="max-w-2xl mb-10">
          <span className="eyebrow">研究类型</span>
          <h2 className="text-3xl font-semibold text-white mt-3">第一版研究类型已统一进入同一工作流</h2>
          <p className="text-sm text-neutral-400 mt-3">每种研究使用对应的模型先验与报告措辞，不再把线下到店或广告行动写成普通商品购买。</p>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Object.entries(STUDY_TYPE_META).map(([key, item]) => (
            <Link key={key} href={`/studies/new?type=${key}`} className="cmai-card p-5 group">
              <div className="flex items-start justify-between">
                <span className="text-2xl">{item.icon}</span>
                <ArrowRight size={15} className="text-neutral-600 group-hover:text-blue-300 transition-colors" />
              </div>
              <h3 className="text-sm font-semibold text-white mt-5">{item.label}</h3>
              <p className="text-xs text-neutral-400 leading-relaxed mt-2">{item.desc}</p>
            </Link>
          ))}
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-5 sm:px-8 pb-20">
        <div className="cmai-card p-7 sm:p-10 grid grid-cols-1 lg:grid-cols-2 gap-10">
          <div>
            <ShieldCheck size={24} className="text-neutral-300" />
            <h2 className="text-2xl font-semibold text-white mt-5">可以立即使用，但不会伪装成销售预测</h2>
            <p className="text-sm text-neutral-400 leading-relaxed mt-3">
              当前产品适合新品筛选、价格比较和竞品情景分析。未接入真实销售或选择实验时，
              报告会把购买率、支付意愿（WTP）和品类渗透率明确标为待验证的先验结果。
            </p>
          </div>
          <div className="space-y-3 text-sm text-neutral-300">
            {[
              "人口与收入：使用泰国国家统计局（NSO）公开宏观数据校准",
              "消费者选择：同时比较您的方案、竞品和不购买",
              "AI 辅助判断：只作参考，不直接冒充真实销量",
              "竞品：公开报价和商家功能声明，不冒充成交数据",
            ].map(item => (
              <div key={item} className="flex items-start gap-2 border-b border-neutral-900 pb-3">
                <Check size={14} className="mt-0.5 text-emerald-400 shrink-0" />
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
            <h2 className="text-3xl font-semibold text-white mt-3">从免费检查到正式决策报告</h2>
            <p className="text-sm text-neutral-400 mt-3">
              基础模拟使用赠送积分；基础决策和深度决策按已购买次数运行。
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <PricingCard
              name="免费预览"
              price="免费"
              note="每个账号 1 次"
              items={["100 人 AI 模拟消费人群", "快速检查输入和研究方向", "不作为正式决策报告"]}
            />
            <PricingCard
              name="基础模拟"
              price="5 积分"
              note="有效邀请码可赠送一次"
              items={["5,000 人 AI 模拟消费人群", "快速比较价格、卖点和方案", "适合日常小范围测试"]}
            />
            <PricingCard
              name="基础决策"
              price="฿990 / 次"
              note="购买 1 次并赠送 1 积分"
              items={["20,000 人 AI 模拟消费人群", "进阶消费者决策模型", "生成基础决策报告"]}
            />
            <PricingCard
              name="深度决策"
              price="฿7,900 / 次起"
              note="深度决策按次数，不扣赠送积分"
              items={["300,000 人 AI 模拟消费人群", "完整竞品、价格与风险分析", "生成正式商业决策报告"]}
              featured
            />
          </div>
          <p className="text-[11px] text-neutral-500 mt-5">
            所有价格以泰铢计；付款由官方销售渠道核验后入账。企业数据校准与历史回测按项目另行签约，不属于当前自助套餐。
          </p>
        </div>
      </section>

      <section className="border-t border-neutral-900">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-16 flex flex-col sm:flex-row sm:items-center justify-between gap-6">
          <div>
            <span className="eyebrow">开始比较方案</span>
            <h2 className="text-2xl font-semibold text-white mt-2">创建第一个泰国消费品研究</h2>
          </div>
          <Link href="/login" className="btn-cmai-primary">
            注册并开始 <ArrowRight size={14} />
          </Link>
        </div>
      </section>

      <footer className="border-t border-neutral-900">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-8 flex flex-col sm:flex-row justify-between gap-4 text-xs text-neutral-500">
          <span>Chiang Mai AI Center · Thailand</span>
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
    </main>
  );
}

function Metric({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="text-2xl sm:text-3xl font-semibold text-white">{value}</div>
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
          <div key={item} className="flex items-start gap-2 text-xs text-neutral-300">
            <Check size={13} className="text-emerald-400 mt-0.5 shrink-0" />
            <span>{item}</span>
          </div>
        ))}
      </div>
      <Link href="/login" className={featured ? "btn-cmai-primary mt-7 w-full" : "btn-cmai-secondary mt-7 w-full"}>
        开始使用
      </Link>
    </div>
  );
}
