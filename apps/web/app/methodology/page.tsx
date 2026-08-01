import Link from "next/link";

export const metadata = { title: "方法与数据 — Chiang Mai AI Center" };

export default function MethodologyPage() {
  return (
    <LegalPage title="算法架构、数据源与决策可靠度保障">
      <Section title="🎯 平台设计初衷">
        为企业出海东南亚提供基于真实大数据的商业推演沙盘。通过将消费者心理特征、收入分布与竞品环境数字化，
        帮助品牌在实际大资本投入前，低成本探明真实市场反应与盈利红线。
      </Section>
      <Section title="🧠 什么是 30 万数字孪生消费者（AI Synthetic Consumers）">
        系统基于泰国国家统计局（NSO）宏观微观快照与全泰 77 府真实人口结构，微观建模出 30 万具有不同年龄、
        职业、家庭收入、居住地与消费偏好的高仿真数字个体。在离散选择模型（DCM）驱动下，真实还原消费博弈全过程。
      </Section>
      <Section title="📊 权威数据源与实时校验">
        人口分布、家庭收入、消费支出与区域粒度精准同步泰国官方统计快照与 WorldPop 100 米高精度人口模型。
        竞品报价与市场参数引入全网动态感知，确保每个演练情景均建立在可靠的数据基底之上。
      </Section>
      <Section title="📐 离散选择模型（Discrete Choice Modeling, DCM）">
        区别于普通 AI 大模型的纯文本生成，系统采用经济学与市场营销学领域的离散选择算法，
        让数字人群在“您的方案、竞品方案、放弃购买”三方博弈中做出现实选择，精准推算价格弹性与最佳转化定价。
      </Section>
      <Section title="📍 高精度商圈与选址分析">
        针对线下餐饮、咖啡馆、酒吧与零售门店，系统实时解析泰国候选点位，依托 500 米粒度的人口分布、
        出行阻力和周边商业竞争强度，科学评估到店意向、客群覆盖率与经营上限。
      </Section>
      <Section title="🔒 算法严谨性与确定性保障">
        拒绝 LLM 凭空幻觉。大语言模型仅在最外层用于整理消费者反馈语气与卖点信号；
        核心的购买率计算、价格弹性与情景排序完全由数学推导与离散选择算法离线演算，确保结果的可追溯性与确定性。
      </Section>
    </LegalPage>
  );
}

function LegalPage({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-base">
      <div className="max-w-3xl mx-auto px-5 py-16">
        <Link href="/" className="text-xs text-neutral-400 hover:text-white">← 返回首页</Link>
        <h1 className="text-3xl font-semibold text-white mt-8 mb-10">{title}</h1>
        <div className="space-y-8">{children}</div>
      </div>
    </main>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="text-base font-semibold text-white">{title}</h2>
      <p className="text-sm text-neutral-400 leading-7 mt-2">{children}</p>
    </section>
  );
}
