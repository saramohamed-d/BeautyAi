"use client";

import { Languages } from "lucide-react";
import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

/** Switches between English and Arabic; the label is the language you'd switch *to*. */
export function LanguageToggle({ className }: { className?: string }) {
  const { locale, setLocale, t } = useI18n();
  const next = locale === "en" ? "ar" : "en";

  return (
    <button
      type="button"
      onClick={() => setLocale(next)}
      aria-label={t("language.switchLabel")}
      lang={next}
      className={cn(
        "inline-flex h-9 items-center gap-1.5 rounded-xl border border-border bg-surface px-3 text-xs font-semibold text-ink hover:border-primary-line",
        className
      )}
    >
      <Languages className="h-4 w-4 text-primary-dark" strokeWidth={1.75} />
      {t(`language.${next}`)}
    </button>
  );
}
