import Link from "next/link";

export const metadata = { title: "隐私与数据安全 — Chiang Mai AI Center" };

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-base">
      <article className="max-w-3xl mx-auto px-5 py-16 text-sm text-neutral-400 leading-7">
        <Link href="/" className="text-xs hover:text-white">← 返回首页</Link>
        <h1 className="text-3xl font-semibold text-white mt-8 mb-8">隐私与企业商业数据安全说明</h1>
        <p>更新日期：2026 年 8 月 1 日</p>
        
        <h2 className="text-white font-semibold mt-8">🔒 企业商业机密隔离与脱敏演算承诺</h2>
        <p className="bg-neutral-900 border border-neutral-800 p-4 rounded-xl text-neutral-200 mt-2">
          客户提交的所有商业产品方案、定价策略、核心卖点、选址位置与竞品参数均属于最高保密级别。
          平台承诺 100% 账号隔离，脱敏离线演算，决不上云公开，绝不将客户项目作为公开案例，也绝不将客户数据用于第三方公共模型训练。
        </p>

        <h2 className="text-white font-semibold mt-8">信息收集与使用规范</h2>
        <p>我们仅保存用于账号认证、项目计算运行、可行性评估报告生成、算力计费核验与必要的安全审计数据。</p>

        <h2 className="text-white font-semibold mt-8">开源架构与客户数据边界</h2>
        <p>平台软件算法源代码开源并不代表客户上传的数据会公开。客户原始商业数据、项目名称、财务策略与生成的评估报告受严密的权限隔离保护，绝不会发布到 GitHub 或其他开源仓库。</p>

        <h2 className="text-white font-semibold mt-8">保存、删除与企业协议</h2>
        <p>
          客户有权随时申请导出或永久销毁账号下的历史项目与数据。企业采购与专属数据安全协议（DPA）可通过{" "}
          <a
            href="https://wa.me/66623458238"
            target="_blank"
            rel="noopener noreferrer"
            className="text-white underline underline-offset-4"
          >
            Lazzor 官方 WhatsApp（+66 62 345 8238）
          </a>
          {" "}联系签定。
        </p>
      </article>
    </main>
  );
}
