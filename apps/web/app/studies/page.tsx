import { AppShell, TopBar } from "@/components/layout";
import { StudiesClient } from "./studies-client";

export const metadata = { title: "研究项目 — Thailand Market Twin" };

export default function StudiesPage() {
  return (
    <AppShell>
      <TopBar
        title="研究项目"
        actions={
          <a href="/studies/new" className="btn-primary">
            <span>+</span> 新建项目
          </a>
        }
      />
      <StudiesClient />
    </AppShell>
  );
}
