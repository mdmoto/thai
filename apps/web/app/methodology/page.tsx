import Link from "next/link";

export const metadata = { title: "方法与数据 — Chiang Mai AI Center" };

export default function MethodologyPage() {
  return (
    <LegalPage title="方法、数据与可信度边界">
      <Section title="产品用途">
        平台用于消费品概念、价格和竞品方案的决策筛选。结果帮助判断下一步优先验证什么，
        不构成销售额、市场份额或投资回报保证。
      </Section>
      <Section title="什么是 AI 模拟消费人群">
        AI 模拟消费人群由系统根据泰国公开人口数据和消费特征建立，技术上也称为 AI 合成消费者。
        它不是 30 万名真人问卷受访者，而是让 AI 在统一规则下模拟不同消费者可能如何选择。
        页面显示的人数代表本次模拟覆盖规模。
      </Section>
      <Section title="数据层">
        泰国地区与府级人口、家庭收入、家庭支出和家庭规模来自版本化公开统计快照。
        心理变量、品牌认知、品类渗透以及没有观测来源的竞品字段会被标记为先验或假设。
      </Section>
      <Section title="选择模型">
        系统会让 AI 模拟消费人群同时比较您的方案、竞品和“不购买”。
        深度决策使用更大的人群规模，并增加价格变化、更多竞品和市场情景分析。
      </Section>
      <Section title="AI 辅助判断的角色">
        AI 用于整理购买理由、拒绝理由和产品卖点信号。它只作为受限制的辅助判断，
        不会把虚拟消费者的回答直接冒充真实市场购买率；不可用时不会影响定量结果。
      </Section>
      <Section title="不确定性">
        在没有真实销售、消费者选择实验或广告对照测试回测前，第 10–90 百分位（P10–P90）
        只是先验预测区间，不是经过验证的销量置信区间。每份报告都会保留数据版本、模型版本和限制。
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
