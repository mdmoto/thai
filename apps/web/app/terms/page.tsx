import Link from "next/link";

export const metadata = { title: "服务条款 — Chiang Mai AI Center" };

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-base">
      <article className="max-w-3xl mx-auto px-5 py-16 text-sm text-neutral-400 leading-7">
        <Link href="/" className="text-xs hover:text-white">← 返回首页</Link>
        <h1 className="text-3xl font-semibold text-white mt-8 mb-8">服务条款</h1>
        <p>更新日期：2026 年 7 月 29 日</p>
        <h2 className="text-white font-semibold mt-8">1. 服务性质</h2>
        <p>本平台提供泰国消费市场的决策支持模拟。输出用于方案比较，不是销量、收益或市场结果保证。</p>
        <h2 className="text-white font-semibold mt-8">2. 用户输入</h2>
        <p>用户应确保有权提交产品、品牌、网址与商业资料，不得提交违法内容、他人机密或受限制的个人信息。用于模型校准的选择数据不得包含姓名、电话、邮箱、完整订单号或其他可识别个人的字段。</p>
        <h2 className="text-white font-semibold mt-8">3. 额度与订单</h2>
        <p>付费订单在官方销售渠道确认到账后入账。基础模拟消耗积分，基础决策与深度决策消耗对应次数；运行失败时，系统会自动退回预留的积分或次数。</p>
        <h2 className="text-white font-semibold mt-8">4. 结果解释</h2>
        <p>报告会区分真实观测数据、待验证的模型先验和大语言模型（LLM）辅助信号。用户应结合实地测试、法律、财务与运营判断作出最终决策。</p>
        <h2 className="text-white font-semibold mt-8">5. 合理使用</h2>
        <p>不得绕过访问控制、滥用计算资源、逆向攻击服务或利用结果实施歧视、欺诈和违法行为。</p>
        <h2 className="text-white font-semibold mt-8">6. 去标识化平台校准</h2>
        <p>
          作为服务质量改进的一部分，使用真实选择数据完成的项目默认贡献去标识化的拟合系数、误差和样本统计，
          用于达到隐私与样本门槛后的平台内部品类基准。原始上传数据、账号、项目名称和报告不会进入该基准，也不会因软件开源而公开。
          企业合同另有约定的，按合同执行。
        </p>
        <h2 className="text-white font-semibold mt-8">7. 联系与企业合同</h2>
        <p>
          企业采购、数据处理条款、服务级别与定制交付以双方签署的订单或合同为准。
          付款和企业采购请通过{" "}
          <a
            href="https://wa.me/66623458238"
            target="_blank"
            rel="noopener noreferrer"
            className="text-white underline underline-offset-4"
          >
            Lazzor 官方 WhatsApp（+66 62 345 8238）
          </a>
          {" "}联系。
        </p>
      </article>
    </main>
  );
}
