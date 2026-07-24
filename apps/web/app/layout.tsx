import type { Metadata } from "next";
import { Geist, Geist_Mono, Space_Grotesk } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Thailand Market Twin Platform | Digital Market Twin in Thailand",
  description:
    "Thailand Digital Market Twin Platform — Put your product, venue or business plan into a digital Thai market built from synthetic consumers.",
  keywords: ["Thailand Market Twin", "Digital Market Twin", "Market Research", "Synthetic Consumers", "Chiang Mai AI"],
  icons: {
    icon: "/favicon.ico",
  },
  openGraph: {
    title: "Thailand Market Twin Platform",
    description: "Digital Market Twin Platform for AI, Startups, and Global Companies entering Thailand.",
    type: "website",
  },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html
      lang={locale}
      className={`${geistSans.variable} ${geistMono.variable} ${spaceGrotesk.variable} h-full antialiased scroll-smooth dark`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col bg-base text-neutral-100 transition-colors duration-300 font-sans">
        <NextIntlClientProvider messages={messages} locale={locale}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
