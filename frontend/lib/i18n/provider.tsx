"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { directionFor, intlTagFor, LOCALE_COOKIE, type Locale } from "@/lib/i18n/config";
import { en } from "@/lib/i18n/messages/en";
import { ar } from "@/lib/i18n/messages/ar";
import type { MessageKey, Messages, ValueSection } from "@/lib/i18n/types";

const DICTIONARIES: Record<Locale, Messages> = { en, ar };

type Vars = Record<string, string | number>;

interface I18nContextValue {
  locale: Locale;
  dir: "ltr" | "rtl";
  setLocale: (locale: Locale) => void;
  /** Translate a key, interpolating `{name}` placeholders from `vars`. */
  t: (key: MessageKey, vars?: Vars) => string;
  /** Label for a raw backend value (e.g. specialty "Dermatology"); falls back to the value itself. */
  label: (section: ValueSection, value: string) => string;
  formatDate: (date: Date, style?: "short" | "long") => string;
  formatTime: (date: Date) => string;
  formatWeekday: (date: Date) => string;
  formatCurrency: (amount: number | string | null | undefined) => string;
  formatNumber: (value: number, fractionDigits?: number) => string;
}

const I18nContext = createContext<I18nContextValue | undefined>(undefined);

function lookup(dict: Messages, key: string): string | undefined {
  let node: unknown = dict;
  for (const part of key.split(".")) {
    if (typeof node !== "object" || node === null) return undefined;
    node = (node as Record<string, unknown>)[part];
  }
  return typeof node === "string" ? node : undefined;
}

function interpolate(template: string, vars?: Vars): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) => (name in vars ? String(vars[name]) : match));
}

export function I18nProvider({ initialLocale, children }: { initialLocale: Locale; children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);

  const setLocale = useCallback((next: Locale) => {
    document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
    document.documentElement.lang = next;
    document.documentElement.dir = directionFor(next);
    setLocaleState(next);
  }, []);

  const value = useMemo<I18nContextValue>(() => {
    const dict = DICTIONARIES[locale];
    const tag = intlTagFor(locale);
    const t = (key: MessageKey, vars?: Vars) => interpolate(lookup(dict, key) ?? lookup(en, key) ?? key, vars);

    return {
      locale,
      dir: directionFor(locale),
      setLocale,
      t,
      label: (section, value) => {
        const labels = dict[section] as Record<string, string>;
        return labels[value] ?? value;
      },
      formatDate: (date, style = "short") =>
        date.toLocaleDateString(tag, style === "long"
          ? { weekday: "long", day: "numeric", month: "long", year: "numeric" }
          : { day: "numeric", month: "short" }),
      formatTime: (date) => date.toLocaleTimeString(tag, { hour: "numeric", minute: "2-digit" }),
      formatWeekday: (date) => date.toLocaleDateString(tag, { weekday: "short" }),
      formatCurrency: (amount) => {
        if (amount === null || amount === undefined) return "—";
        const num = typeof amount === "string" ? parseFloat(amount) : amount;
        if (Number.isNaN(num)) return "—";
        return t("common.currency", { amount: num.toLocaleString(tag) });
      },
      formatNumber: (num, fractionDigits = 0) =>
        num.toLocaleString(tag, { minimumFractionDigits: fractionDigits, maximumFractionDigits: fractionDigits }),
    };
  }, [locale, setLocale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}
