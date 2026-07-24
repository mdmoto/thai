import { Suspense } from "react";
import { AppShell, TopBar } from "@/components/layout";
import { Card } from "@/components/ui";
import { StudyViewClient } from "./view-client";

export const metadata = { title: "项目详情 — Thailand Market Twin" };

export default function StudyViewPage() {
  return (
    <AppShell>
      <TopBar title="项目详情" />
      <Suspense
        fallback={
          <div className="p-8">
            <Card>正在读取项目…</Card>
          </div>
        }
      >
        <StudyViewClient />
      </Suspense>
    </AppShell>
  );
}
