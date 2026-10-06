"use client";

import { Check } from "lucide-react";
import { AVATAR_KEYS, DoctorAvatar } from "@/components/doctors/doctor-avatar";
import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

/** Grid of the illustrated avatars; the chosen one gets a pink ring and a tick. */
export function AvatarPicker({ value, onChange }: { value: string | null | undefined; onChange: (key: string) => void }) {
  const { t } = useI18n();
  return (
    <fieldset>
      <legend className="text-xs font-medium text-ink-muted">{t("avatar.choose")}</legend>
      <div className="mt-2 grid grid-cols-4 gap-3">
        {AVATAR_KEYS.map((key, index) => {
          const selected = value === key;
          return (
            <button
              key={key}
              type="button"
              onClick={() => onChange(key)}
              aria-pressed={selected}
              aria-label={t("avatar.option", { number: index + 1 })}
              className={cn(
                "relative mx-auto rounded-full p-0.5 transition-transform hover:scale-105",
                selected ? "ring-2 ring-primary ring-offset-2" : "ring-1 ring-border"
              )}
            >
              <DoctorAvatar avatar={key} size="md" className="ring-0" />
              {selected && (
                <span className="absolute -end-1 -top-1 grid h-5 w-5 place-items-center rounded-full bg-primary text-white">
                  <Check className="h-3 w-3" strokeWidth={3} />
                </span>
              )}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
