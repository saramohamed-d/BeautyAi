/**
 * Locale configuration.
 *
 * English is the default; Arabic is a full alternative (RTL). The
 * chosen locale lives in a cookie so the server-rendered <html lang dir>
 * is correct on first paint (no LTR→RTL flash), and the root layout
 * reads it via next/headers. No URL prefix (/en, /ar): every page is a
 * client component already, so a cookie avoids restructuring routes.
 */
export const LOCALES = ["en", "ar"] as const;
export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "en";
export const LOCALE_COOKIE = "locale";

export function isLocale(value: string | undefined | null): value is Locale {
  return LOCALES.includes(value as Locale);
}

export function directionFor(locale: Locale): "ltr" | "rtl" {
  return locale === "ar" ? "rtl" : "ltr";
}

/** BCP 47 tag used for Intl date/number formatting. */
export function intlTagFor(locale: Locale): string {
  return locale === "ar" ? "ar-EG" : "en-US";
}
