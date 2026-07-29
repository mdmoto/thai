import Link from "next/link";

export const metadata = { title: "隐私说明 — Chiang Mai AI Center" };

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-base">
      <article className="max-w-3xl mx-auto px-5 py-16 text-sm text-neutral-400 leading-7">
        <Link href="/" className="text-xs hover:text-white">← 返回首页</Link>
        <h1 className="text-3xl font-semibold text-white mt-8 mb-8">隐私说明</h1>
        <p>更新日期：2026 年 7 月 29 日</p>
        <h2 className="text-white font-semibold mt-8">收集的信息</h2>
        <p>我们保存账号邮箱、邮箱验证状态、姓名、公司、项目输入、报告、额度流水和订单状态；为防止批量注册和滥用，还会短期保存经过不可逆处理的网络安全标识。</p>
        <h2 className="text-white font-semibold mt-8">不应提交的信息</h2>
        <p>请勿上传身份证件、支付卡信息、医疗资料、客户姓名、电话、邮箱、完整订单号或未经授权的个人数据。选择数据只需要匿名选择组、是否选择以及价格和产品属性。</p>
        <h2 className="text-white font-semibold mt-8">使用目的</h2>
        <p>信息用于认证、项目运行、报告保存、计费核验、安全审计、产品支持和模型质量改进，不会把客户项目作为公开案例。</p>
        <h2 className="text-white font-semibold mt-8">平台长期校准</h2>
        <p>
          若项目使用真实选择数据完成拟合，系统默认只提取品类、研究类型、样本数量、拟合系数和误差范围，
          用于形成平台内部的泰国品类基准。上传的原始行、客户账号、项目名称、报告内容和选择组编号不会进入该基准；
          选择组和选项编号会在保存前重新编号。达到至少 5 个独立贡献和 500 个选择组前，平台不会启用聚合基准。
        </p>
        <h2 className="text-white font-semibold mt-8">开源代码与客户数据</h2>
        <p>软件源代码可以公开，不代表客户上传的数据会进入代码仓库或向公众开放。客户原始数据不会发布到 GitHub 或其他开源仓库。</p>
        <h2 className="text-white font-semibold mt-8">第三方处理</h2>
        <p>基础设施、模型、邮件投递和防机器人服务供应商可能仅为提供服务、安全验证与验证码投递而处理必要数据。企业客户可另行签署数据处理协议。</p>
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
