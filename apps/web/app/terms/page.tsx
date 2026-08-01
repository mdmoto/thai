import Link from "next/link";

export const metadata = { title: "服务条款与算力规范 — Chiang Mai AI Center" };

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-base">
      <article className="max-w-3xl mx-auto px-5 py-16 text-sm text-neutral-400 leading-7">
        <Link href="/" className="text-xs hover:text-white">← 返回首页</Link>
        <h1 className="text-3xl font-semibold text-white mt-8 mb-8">服务条款与算力消费规范</h1>
        <p>更新日期：2026 年 8 月 1 日</p>
        
        <h2 className="text-white font-semibold mt-8">1. 商业推演服务性质</h2>
        <p>本平台基于泰国全域宏观人口建模与离散选择算法，为企业出海东南亚提供科学的市场可行性、产品定价与商圈选址推演服务。推演研报旨在协助决策团队评估风险与机会，建立控错红线。</p>
        
        <h2 className="text-white font-semibold mt-8">2. 算力包与计费规则</h2>
        <p>基础模拟消耗积分，基础决策与深度决策消耗对应订阅次数。若遇到系统性错误导致推演未完成，系统将自动原路退回消耗的算力积分或次数。</p>

        <h2 className="text-white font-semibold mt-8">3. 严严谨性与数理算法保障</h2>
        <p>生成的商业评估报告基于权威统计快照与多阶段决策模型。建议企业结合线上线下实测数据、法律合规与财务预算做出最终投产决策。</p>

        <h2 className="text-white font-semibold mt-8">4. 企业合同与专属支持</h2>
        <p>
          大客户采购、对公对海外支付、定制交付与 SLA 保障以双方签署的专属合同为准。
          商务联系请通过{" "}
          <a
            href="https://wa.me/66623458238"
            target="_blank"
            rel="noopener noreferrer"
            className="text-white underline underline-offset-4"
          >
            Lazzor 官方 WhatsApp（+66 62 345 8238）
          </a>
          {" "}洽谈。
        </p>
      </article>
    </main>
  );
}
