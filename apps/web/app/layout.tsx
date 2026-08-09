import type { Metadata } from "next";
import production from "@/deployment/production.json";
import "./globals.css";

const geistSans = { variable: "font-sans" };
const geistMono = { variable: "font-mono" };

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL || production.siteOrigin,
  ),
  title: "Chiang Mai AI Center | 泰国商业决策平台",
  description:
    "让30万人的 AI 模拟消费人群先替您试一遍。比较产品、价格、广告、选址和经营方案，再决定钱该花在哪里。",
  keywords: ["CMAI", "Thailand Market Twin", "泰国市场研究", "消费品定价", "门店选址", "广告测试", "Thailand Market Entry"],
  icons: {
    icon: "/favicon.ico",
  },
  openGraph: {
    title: "Chiang Mai AI Center | 泰国商业决策平台",
    description: "30万 AI 模拟消费人群：先模拟，再决策。",
    type: "website",
    images: [{ url: "/og-v2.png", width: 1200, height: 630, alt: "30万 AI 模拟消费人群：先模拟，再决策" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Chiang Mai AI Center | 泰国商业决策平台",
    description: "30万 AI 模拟消费人群：先模拟，再决策。",
    images: ["/og-v2.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased scroll-smooth dark`}
      suppressHydrationWarning
    >
      <head>
        <link rel="dns-prefetch" href="https://lazzor.com" />
        <link rel="preconnect" href="https://lazzor.com" crossOrigin="anonymous" />
        <link rel="prefetch" href="https://lazzor.com" />
      </head>
      <body className="min-h-full flex flex-col bg-base text-neutral-100 transition-colors duration-300 font-sans">
        {children}
      </body>
    </html>
  );
}
