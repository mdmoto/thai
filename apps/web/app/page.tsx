import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  Check,
  Database,
  GitCompareArrows,
  ShieldCheck,
} from "lucide-react";

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
      <header className="max-w-7xl mx-auto px-5 sm:px-8 h-16 flex items-center justify-between border-b border-neutral-900">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="w-8 h-8 rounded-lg bg-neutral-900 border border-neutral-800 flex items-center justify-center text-xs font-semibold">
            MT
          </span>
          <span className="text-sm font-semibold">Thailand Market Twin</span>
        </Link>
        <nav className="flex items-center gap-2">
          <Link href="/methodology" className="btn-cmai-ghost hidden sm:inline-flex">
            方法与数据
          </Link>
          <Link href="/login" className="btn-cmai-secondary">登录</Link>
          <Link href="/studies/new?type=PRODUCT_VALIDATION" className="btn-cmai-primary">
            开始测试
          </Link>
        </nav>
      </header>

      <section className="max-w-7xl mx-auto px-5 sm:px-8 pt-20 pb-16">
        <div className="max-w-4xl">
          <span className="eyebrow">Thailand consumer decision platform</span>
          <h1 className="text-4xl sm:text-6xl font-semibold tracking-tight leading-[1.05] text-white mt-5">
            进入泰国市场前，
            <br />
            先比较产品、价格与竞品情景
          </h1>
          <p className="text-base sm:text-lg text-neutral-400 leading-relaxed max-w-2xl mt-6">
            面向进入泰国市场的消费品牌。用版本化人口、竞品报价、选择模型和情景模拟，
            快速筛选更值得验证的商业方案。
          </p>
          <div className="flex flex-wrap gap-3 mt-8">
            <Link href="/studies/new?type=PRODUCT_VALIDATION&category=PET_WATER_FOUNTAIN" className="btn-cmai-primary">
              体验宠物饮水机模板 <ArrowRight size={14} />
            </Link>
            <Link href="/methodology" className="btn-cmai-secondary">
              查看可信度边界
            </Link>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-2 mt-8 text-xs text-neutral-500">
            <span className="flex items-center gap-1.5"><Check size={13} /> 泰国 77 府人口覆盖</span>
            <span className="flex items-center gap-1.5"><Check size={13} /> 竞品与不购买选项</span>
            <span className="flex items-center gap-1.5"><Check size={13} /> 不把 LLM 投票当销量</span>
            <span className="flex items-center gap-1.5"><Check size={13} /> 报告记录假设和版本</span>
          </div>
        </div>
      </section>

      <section className="border-y border-neutral-900 bg-[#0d0d0d]">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-12 grid grid-cols-2 lg:grid-cols-4 gap-6">
          <Metric value="77" label="泰国府级人口覆盖" />
          <Metric value="15" label="首个品类公开报价" />
          <Metric value="5" label="Professional 竞品选择集" />
          <Metric value="P10–P90" label="明确标记的先验预测区间" />
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-5 sm:px-8 py-20">
        <div className="max-w-2xl mb-10">
          <span className="eyebrow">How it works</span>
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
        <div className="cmai-card p-7 sm:p-10 grid grid-cols-1 lg:grid-cols-2 gap-10">
          <div>
            <ShieldCheck size={24} className="text-neutral-300" />
            <h2 className="text-2xl font-semibold text-white mt-5">可以立即使用，但不会伪装成销售预测</h2>
            <p className="text-sm text-neutral-400 leading-relaxed mt-3">
              当前产品适合新品筛选、价格比较和竞品情景分析。未接入真实销售或选择实验时，
              报告会把购买率、WTP 和品类渗透标为先验结果。
            </p>
          </div>
          <div className="space-y-3 text-sm text-neutral-300">
            {[
              "人口与收入：泰国 NSO 公开宏观数据校准",
              "选择概率：MNL / 计划对应的异质性模型",
              "LLM：仅提供有限权重的结构化弱信号",
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
            <span className="eyebrow">Simple pricing</span>
            <h2 className="text-3xl font-semibold text-white mt-3">从免费检查到正式决策报告</h2>
            <p className="text-sm text-neutral-400 mt-3">
              套餐差异来自样本、竞品数量、模型深度和不确定性轮数，不是简单更换大模型。
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <PricingCard
              name="Preview"
              price="免费"
              note="每个账号 1 次"
              items={["100 合成人口", "40 轮 Monte Carlo", "用于检查输入方向"]}
            />
            <PricingCard
              name="Standard"
              price="5 积分"
              note="注册即赠送一次"
              items={["10,000 合成人口", "80 轮 Monte Carlo", "3 个竞品选择方案"]}
            />
            <PricingCard
              name="Professional"
              price="฿7,900"
              note="含 20 积分 / 1 次正式运行"
              items={["30,000 合成人口", "150 轮 Monte Carlo", "5 个竞品与完整情景分析"]}
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
            <span className="eyebrow">Ready to compare</span>
            <h2 className="text-2xl font-semibold text-white mt-2">创建第一个泰国消费品研究</h2>
          </div>
          <Link href="/login" className="btn-cmai-primary">
            注册并开始 <ArrowRight size={14} />
          </Link>
        </div>
      </section>

      <footer className="border-t border-neutral-900">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-8 flex flex-col sm:flex-row justify-between gap-4 text-xs text-neutral-500">
          <span>Thailand Market Twin · A decision-support product by Lazzor</span>
          <div className="flex gap-4">
            <Link href="/methodology">方法</Link>
            <Link href="/terms">条款</Link>
            <Link href="/privacy">隐私</Link>
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
