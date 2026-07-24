import Link from "next/link";

export const metadata = { title: "隐私说明 — Thailand Market Twin" };

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-base">
      <article className="max-w-3xl mx-auto px-5 py-16 text-sm text-neutral-400 leading-7">
        <Link href="/" className="text-xs hover:text-white">← 返回首页</Link>
        <h1 className="text-3xl font-semibold text-white mt-8 mb-8">隐私说明</h1>
        <p>更新日期：2026 年 7 月 24 日</p>
        <h2 className="text-white font-semibold mt-8">收集的信息</h2>
        <p>我们保存账号邮箱、姓名、公司、项目输入、报告、额度流水和订单状态，以提供工作区与交付服务。</p>
        <h2 className="text-white font-semibold mt-8">不应提交的信息</h2>
        <p>请勿上传身份证件、支付卡信息、医疗资料或未经授权的个人数据。当前产品不需要这些信息。</p>
        <h2 className="text-white font-semibold mt-8">使用目的</h2>
        <p>信息用于认证、项目运行、报告保存、计费核验、安全审计和产品支持，不会把客户项目作为公开案例。</p>
        <h2 className="text-white font-semibold mt-8">第三方处理</h2>
        <p>基础设施和模型供应商可能仅为提供服务而处理必要数据。企业客户可另行签署数据处理协议。</p>
        <h2 className="text-white font-semibold mt-8">保存与删除</h2>
        <p>
          数据按提供服务和履行合同所需期限保存。删除、导出或企业隐私请求可通过{" "}
          <a
            href="https://wa.me/66623458238"
            target="_blank"
            rel="noopener noreferrer"
            className="text-white underline underline-offset-4"
          >
            Lazzor 官方 WhatsApp（+66 62 345 8238）
          </a>
          {" "}提交。
        </p>
        <h2 className="text-white font-semibold mt-8">安全</h2>
        <p>平台使用账号隔离、哈希密码、签名令牌、受保护管理接口和服务端订单核验；任何互联网服务仍无法承诺绝对安全。</p>
      </article>
    </main>
  );
}
