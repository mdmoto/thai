import Link from "next/link";
import { AppShell, TopBar } from "@/components/layout";
import { ReportClient } from "@/app/studies/[id]/report/report-client";

export const metadata = {
  title: "宠物智能饮水机样例报告 — Chiang Mai AI Center",
  description: "查看泰国宠物智能饮水机 AI 市场模拟的完整固定样例报告。",
};

export default function PetWaterDemoPage() {
  return (
    <AppShell>
      <TopBar
        title="📊 泰国宠物智能饮水机 · 出海可行性评估报告"
        actions={(
          <Link
            href="/studies/new?type=PRODUCT_VALIDATION&category=PET_WATER_FOUNTAIN"
            className="btn-cmai-primary"
          >
            用自己的数据测试
          </Link>
        )}
      />
      <div className="border-b border-blue-400/15 bg-blue-500/5 px-5 sm:px-8 py-3 text-xs text-blue-100/80">
        💡 企业级精选案例报告：基于 10,000 名高仿真数字消费者在泰国宠物智能饮水机市场的真实对抗推演。
      </div>
      <ReportClient publicReportUrl="/demo/pet-water-standard-v1.json" />
    </AppShell>
  );
}
