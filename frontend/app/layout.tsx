import type { Metadata } from "next";
import { Cairo } from "next/font/google";
import "./globals.css";
import { Providers } from "@/app/providers";
import { Navbar } from "@/components/layout/navbar";
import { Footer } from "@/components/layout/footer";

const cairo = Cairo({
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-cairo",
  display: "swap",
});

export const metadata: Metadata = {
  title: "BeautyAI — منصة التجميل والجلدية",
  description: "منصة ذكاء اصطناعي لربط المرضى بأطباء وعيادات التجميل والجلدية المعتمدة في مصر والوطن العربي.",
};

/**
 * Root layout.
 *
 * dir="rtl" / lang="ar" is the whole app's baseline (Sprint 0 decision,
 * preserved here) — this is an Arabic-first product, not an English
 * product with an Arabic toggle. Flexbox/grid layouts throughout the app
 * rely on the browser's native RTL handling rather than manual mirroring.
 *
 * PatientProvider and BookingProvider are mounted here (not per-page) so
 * their in-memory state survives client-side navigation between
 * /booking -> /payment and across the whole session for the "logged in"
 * patient placeholder — see lib/booking-context.tsx and
 * lib/patient-context.tsx for why this is in-memory only, not real auth.
 */
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ar" dir="rtl" className={cairo.variable}>
      <body className="flex min-h-dvh flex-col bg-bg font-sans text-ink antialiased">
        <Providers>
          <Navbar />
          <main className="flex-1">{children}</main>
          <Footer />
        </Providers>
      </body>
    </html>
  );
}
