import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import production from "@/deployment/production.json";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL || production.siteOrigin,
  ),
  title: "CMAI Thailand Market Twin | 泰国市场决策平台",
  description:
    "面向进入泰国市场的品牌与线下商业，比较产品、价格、广告、商圈、门店和经营情景，并披露数据来源、模型版本与可信度边界。",
  keywords: ["CMAI", "Thailand Market Twin", "泰国市场研究", "消费品定价", "门店选址", "广告测试", "Thailand Market Entry"],
  icons: {
    icon: "/favicon.ico",
  },
  openGraph: {
    title: "CMAI Thailand Market Twin | 泰国市场决策平台",
    description: "进入泰国市场前，先比较产品、价格、广告、选址与经营情景。",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Thailand Market Twin" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "CMAI Thailand Market Twin | 泰国市场决策平台",
    description: "进入泰国市场前，先比较产品、价格、广告、选址与经营情景。",
    images: ["/og.png"],
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
      <body className="min-h-full flex flex-col bg-base text-neutral-100 transition-colors duration-300 font-sans">
        {children}
      </body>
    </html>
  );
}
