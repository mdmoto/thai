import { Suspense } from "react";
import { AppShell, TopBar } from "@/components/layout";
import { NewStudyWizard } from "./wizard-client";
import { Spinner } from "@/components/ui";

export const metadata = { title: "新建项目 — Chiang Mai AI Center" };

export default function NewStudyPage() {
  return (
    <AppShell>
      <TopBar title="只需 5 分钟，配置您的泰国商业出海沙盘" />
      <Suspense fallback={<div className="flex justify-center py-20"><Spinner size={24} /></div>}>
        <NewStudyWizard />
      </Suspense>
    </AppShell>
  );
}
