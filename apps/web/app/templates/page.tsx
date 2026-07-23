import { AppShell, TopBar } from "@/components/layout";
import { TemplatesClient } from "./templates-client";

export const metadata = { title: "模板库 — Thailand Market Twin" };

export default function TemplatesPage() {
  return (
    <AppShell>
      <TopBar title="模板库" />
      <TemplatesClient />
    </AppShell>
  );
}
