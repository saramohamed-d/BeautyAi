"use client";

import { Logo } from "@/components/layout/logo";
import { useI18n } from "@/lib/i18n/provider";

/** Desktop-only footer; on phones the tab bar takes this space. */
export function Footer() {
  const { t } = useI18n();
  return (
    <footer className="hidden border-t border-border bg-surface md:block">
      <div className="mx-auto flex max-w-5xl flex-col gap-2 px-[18px] py-8">
        <Logo className="text-xl" />
        <p className="max-w-md text-sm text-ink-muted">{t("footer.tagline")}</p>
        <p className="text-sm text-ink-muted">{t("footer.disclaimer")}</p>
        <p className="mt-2 text-xs text-ink-muted">{t("footer.rights", { year: new Date().getFullYear() })}</p>
      </div>
    </footer>
  );
}
