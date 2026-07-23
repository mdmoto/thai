import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import "./globals.css";

export const metadata: Metadata = {
  title: "Thailand Market Twin — 泰国数字市场孪生平台",
  description:
    "把产品、门店或经营方案放入由泰国合成消费者构成的数字市场中，比较不同方案的商业结果。",
  keywords: ["泰国市场", "市场模拟", "消费者分析", "Thailand market", "market research"],
  openGraph: {
    title: "Thailand Market Twin",
    description: "泰国数字市场孪生平台 — 比较方案，发现机会",
    type: "website",
    locale: "zh_CN",
  },
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale} suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Noto+Sans+SC:wght@300;400;500;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <NextIntlClientProvider messages={messages} locale={locale}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
