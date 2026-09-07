import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/app/providers";

export const metadata: Metadata = {
  title: "BeautyAI",
  description: "AI-powered platform connecting patients with verified aesthetic and dermatology clinics",
};

/**
 * Root layout.
 *
 * Design decision: `dir="rtl"` is hardcoded here for Sprint 0. Real
 * locale detection (from user preference, Accept-Language header, or a
 * /ar /en route prefix) is a Sprint 3/4 concern once the i18n strategy is
 * decided — flagged in docs/architecture.md as an open decision. Sprint 0
 * just proves the RTL layout pipeline works end-to-end (Tailwind logical
 * utilities + native `dir`) with placeholder content.
 */
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ar" dir="rtl">
      <body className="font-arabic bg-white text-gray-900 antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
