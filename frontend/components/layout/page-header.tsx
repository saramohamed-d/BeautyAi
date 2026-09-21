"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { useI18n } from "@/lib/i18n/provider";

/**
 * Back arrow + centered title (the demo's `.back` / `.title`). With
 * `backHref` the arrow is a real link; with `onBack` it runs a handler
 * (e.g. previous wizard step); otherwise it goes back in history.
 * The chevron flips in RTL.
 */
export function PageHeader({ title, backHref, onBack }: { title: string; backHref?: string; onBack?: () => void }) {
  const { t } = useI18n();
  const router = useRouter();
  const icon = <ChevronLeft className="h-6 w-6 rtl:rotate-180" strokeWidth={2} />;
  const buttonClass = "grid h-10 w-10 place-items-center rounded-xl text-ink hover:bg-primary-soft/60";

  return (
    <div className="relative mb-4 flex h-10 items-center">
      {backHref ? (
        <Link href={backHref} aria-label={t("common.back")} className={buttonClass}>
          {icon}
        </Link>
      ) : (
        <button type="button" aria-label={t("common.back")} onClick={onBack ?? (() => router.back())} className={buttonClass}>
          {icon}
        </button>
      )}
      <h1 className="pointer-events-none absolute inset-x-12 text-center text-sm font-bold text-ink">{title}</h1>
    </div>
  );
}
