import { AppShell, TopBar } from "@/components/layout";
import { BillingClient } from "./billing-client";

export const metadata = { title: "额度与订单 — Thailand Market Twin" };

export default function BillingPage() {
  return (
    <AppShell>
      <TopBar title="额度与订单" />
      <BillingClient />
    </AppShell>
  );
}
