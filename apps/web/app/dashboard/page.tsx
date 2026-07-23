import { AppShell, TopBar } from "@/components/layout";
import { DashboardClient } from "./dashboard-client";

export const metadata = {
  title: "控制台 — Thailand Market Twin",
};

export default function DashboardPage() {
  return (
    <AppShell>
      <TopBar
        title="控制台"
        actions={
          <a href="/studies/new" className="btn-primary">
            <span>+</span> 新建项目
          </a>
        }
      />
      <DashboardClient />
    </AppShell>
  );
}
