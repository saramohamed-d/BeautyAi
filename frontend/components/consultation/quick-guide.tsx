"use client";

import { useState } from "react";
import { Button, LinkButton } from "@/components/ui/button";
import { CONCERNS, type ConcernId } from "@/lib/concerns";
import { useI18n } from "@/lib/i18n/provider";
import { withNext } from "@/lib/safe-next";
import { cn } from "@/lib/utils";

/**
 * For visitors: pick a topic, then log in to start the AI consultation
 * about it (the first message is prefilled). Since Sprint 9 there's no
 * fixed concern → specialty answer; the consultation provides it.
 */
export function QuickGuide() {
  const { t } = useI18n();
  const [selected, setSelected] = useState<ConcernId | null>(null);

  return (
    <>
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3" role="radiogroup" aria-label={t("consult.subtitle")}>
        {CONCERNS.map(({ id, icon: Icon }) => {
          const isSelected = selected === id;
          return (
            <button
              key={id}
              type="button"
              role="radio"
              aria-checked={isSelected}
              onClick={() => setSelected(id)}
              className={cn(
                "flex flex-col items-center gap-3 rounded-tile border px-2 py-4 text-sm font-medium text-ink transition-colors",
                isSelected ? "border-primary-accent bg-primary-soft" : "border-border bg-surface hover:border-primary-line"
              )}
            >
              <Icon className={cn("h-6 w-6", isSelected ? "text-primary-dark" : "text-ink-muted")} strokeWidth={1.5} />
              {t(`concerns.${id}`)}
            </button>
          );
        })}
      </div>
      {selected ? (
        <LinkButton href={withNext("/login", `/consultation?topic=${selected}`)} block className="mt-[15px]">
          {t("consultation.startWith", { concern: t(`concerns.${selected}`) })}
        </LinkButton>
      ) : (
        <Button block className="mt-[15px]" disabled>
          {t("common.continue")}
        </Button>
      )}
    </>
  );
}
