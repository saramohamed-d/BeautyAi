import type { Metadata } from "next";
import { cookies } from "next/headers";
import { Cairo, DM_Sans, Playfair_Display } from "next/font/google";
import "./globals.css";
import { Providers } from "@/app/providers";
import { Navbar } from "@/components/layout/navbar";
import { Footer } from "@/components/layout/footer";
import { BottomNav } from "@/components/layout/bottom-nav";
import { RoleRedirect } from "@/components/layout/role-redirect";
import { DEFAULT_LOCALE, directionFor, isLocale, LOCALE_COOKIE } from "@/lib/i18n/config";

const dmSans = DM_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-dm-sans",
  display: "swap",
});

const playfair = Playfair_Display({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-playfair",
  display: "swap",
});

const cairo = Cairo({
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-cairo",
  display: "swap",
});

export const metadata: Metadata = {
  title: "BeautyAI",
  description: "AI-powered platform connecting patients with verified aesthetic and dermatology doctors and clinics.",
};

/**
 * Root layout.
 *
 * English is the default language; Arabic is available from the
 * language toggle. The choice is stored in a cookie and read here, so
 * <html lang dir> is right in the server-rendered HTML — no flash of the
 * wrong direction. Layout uses logical utilities (ms-/ps-/start-/text-start)
 * so the same markup mirrors correctly in RTL.
 *
 * AuthProvider and BookingProvider (inside Providers) are mounted here so
 * their state survives client-side navigation — see lib/auth-context.tsx
 * and lib/booking-context.tsx.
 */
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const cookieLocale = cookies().get(LOCALE_COOKIE)?.value;
  const locale = isLocale(cookieLocale) ? cookieLocale : DEFAULT_LOCALE;

  return (
    <html lang={locale} dir={directionFor(locale)} className={`${dmSans.variable} ${cairo.variable} ${playfair.variable}`}>
      <body className="flex min-h-dvh flex-col font-sans text-ink antialiased">
        <Providers locale={locale}>
          <RoleRedirect />
          <Navbar />
          <main className="mx-auto w-full max-w-[430px] flex-1 md:max-w-none">{children}</main>
          <Footer />
          <BottomNav />
        </Providers>
      </body>
    </html>
  );
}
