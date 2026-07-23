import { Suspense } from "react";
import { AppShell, TopBar } from "@/components/layout";
import { NewStudyWizard } from "./wizard-client";
import { Spinner } from "@/components/ui";

export const metadata = { title: "新建项目 — Thailand Market Twin" };

export default function NewStudyPage() {
  return (
    <AppShell>
      <TopBar title="新建研究项目" />
      <Suspense fallback={<div className="flex justify-center py-20"><Spinner size={24} /></div>}>
        <NewStudyWizard />
      </Suspense>
    </AppShell>
  );
}
