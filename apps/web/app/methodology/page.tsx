import Link from "next/link";

export const metadata = { title: "方法与数据 — Thailand Market Twin" };

export default function MethodologyPage() {
  return (
    <LegalPage title="方法、数据与可信度边界">
      <Section title="产品用途">
        平台用于消费品概念、价格和竞品方案的决策筛选。结果帮助判断下一步优先验证什么，
        不构成销售额、市场份额或投资回报保证。
      </Section>
      <Section title="数据层">
        泰国地区与府级人口、家庭收入、家庭支出和家庭规模来自版本化公开统计快照。
        心理变量、品牌认知、品类渗透以及没有观测来源的竞品字段会被标记为先验或假设。
      </Section>
      <Section title="选择模型">
        定量核心使用包含焦点产品、竞品和“不购买”选项的离散选择模型。
        Professional 增加更大样本、更多竞品、价格弹性和情景分析。
      </Section>
      <Section title="LLM 的角色">
        LLM 用于结构化购买理由、拒绝理由和属性信号。它具有明确权重上限，
        不会把虚拟消费者投票直接平均成市场购买率；不可用时权重为零。
      </Section>
      <Section title="不确定性">
        在没有真实销售、选择实验或 A/B 回测前，P10–P90 为先验预测区间，
        不是经过验证的置信区间。每份报告都会保留数据版本、模型版本和限制。
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
