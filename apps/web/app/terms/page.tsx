import Link from "next/link";

export const metadata = { title: "服务条款 — Thailand Market Twin" };

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-base">
      <article className="max-w-3xl mx-auto px-5 py-16 text-sm text-neutral-400 leading-7">
        <Link href="/" className="text-xs hover:text-white">← 返回首页</Link>
        <h1 className="text-3xl font-semibold text-white mt-8 mb-8">服务条款</h1>
        <p>更新日期：2026 年 7 月 24 日</p>
        <h2 className="text-white font-semibold mt-8">1. 服务性质</h2>
        <p>本平台提供泰国消费市场的决策支持模拟。输出用于方案比较，不是销量、收益或市场结果保证。</p>
        <h2 className="text-white font-semibold mt-8">2. 用户输入</h2>
        <p>用户应确保有权提交产品、品牌、网址与商业资料，不得提交违法内容、他人机密或受限制的个人信息。</p>
        <h2 className="text-white font-semibold mt-8">3. 额度与订单</h2>
        <p>付费订单在官方销售渠道确认到账后入账。失败运行的预留积分会自动退回；已经完成并生成报告的运行会消耗对应额度。</p>
        <h2 className="text-white font-semibold mt-8">4. 结果解释</h2>
        <p>报告会区分观测数据、模型先验和 LLM 弱信号。用户应结合实地测试、法律、财务与运营判断作出最终决策。</p>
        <h2 className="text-white font-semibold mt-8">5. 合理使用</h2>
        <p>不得绕过访问控制、滥用计算资源、逆向攻击服务或利用结果实施歧视、欺诈和违法行为。</p>
        <h2 className="text-white font-semibold mt-8">6. 联系与企业合同</h2>
        <p>企业采购、数据处理条款、服务级别与定制交付以双方签署的订单或合同为准。</p>
      </article>
    </main>
  );
}
