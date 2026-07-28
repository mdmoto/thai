import { AppShell, TopBar } from "@/components/layout";
import { AdminClient } from "./admin-client";

export const metadata = {
  title: "管理后台 — Chiang Mai AI Center",
};

export default function AdminPage() {
  return (
    <AppShell>
      <TopBar title="管理后台" />
      <AdminClient />
    </AppShell>
  );
}
