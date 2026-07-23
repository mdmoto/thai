import { AppShell, TopBar } from "@/components/layout";
import { NewStudyWizard } from "./wizard-client";

export const metadata = { title: "新建项目 — Thailand Market Twin" };

export default function NewStudyPage() {
  return (
    <AppShell>
      <TopBar title="新建研究项目" />
      <NewStudyWizard />
    </AppShell>
  );
}
