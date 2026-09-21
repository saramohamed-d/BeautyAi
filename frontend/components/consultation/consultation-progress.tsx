"use client";

import { Check } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import { REQUIRED_FIELDS } from "@/types/chat";

/** Which of the four required consultation details are known (the demo's progress bar). */
export function ConsultationProgress({ missing }: { missing: string[] }) {
  const { t } = useI18n();
  const done = REQUIRED_FIELDS.filter((field) => !missing.includes(field)).length;

  return (
    <div className="mb-3">
      <p className="text-xs font-semibold text-ink-muted">
        {t("consultation.progress", { done, total: REQUIRED_FIELDS.length })}
      </p>
      <Progress value={(done / REQUIRED_FIELDS.length) * 100} label={t("consultation.progress", { done, total: REQUIRED_FIELDS.length })} />
      <div className="-mt-1 flex flex-wrap gap-1.5">
        {REQUIRED_FIELDS.map((field) => {
          const known = !missing.includes(field);
          return (
            <span
              key={field}
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold",
                known ? "bg-primary-soft text-primary-dark" : "border border-border text-ink-muted"
              )}
            >
              {known && <Check className="h-3 w-3" aria-hidden="true" />}
              {t(`consultation.fields.${field}`)}
            </span>
          );
        })}
      </div>
    </div>
  );
}
