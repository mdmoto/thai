import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
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
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "https://ai.lazzor.com"),
  title: "Thailand Market Twin | 泰国消费品市场决策平台",
  description:
    "面向进入泰国市场的消费品牌，比较产品、价格、竞品和目标人群情景，并披露数据来源、模型版本与可信度边界。",
  keywords: ["Thailand Market Twin", "泰国市场研究", "消费品定价", "离散选择模型", "Thailand Market Entry"],
  icons: {
    icon: "/favicon.ico",
  },
  openGraph: {
    title: "Thailand Market Twin | 泰国消费品市场决策平台",
    description: "进入泰国市场前，先比较产品、价格与竞品情景。",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Thailand Market Twin" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Thailand Market Twin | 泰国消费品市场决策平台",
    description: "进入泰国市场前，先比较产品、价格与竞品情景。",
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
