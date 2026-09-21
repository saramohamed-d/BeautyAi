"use client";

import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import type { Availability } from "@/types/availability";

export function TimeSlotGrid({
  slots,
  selectedSlot,
  onSelect,
}: {
  slots: Availability[];
  selectedSlot: Availability | null;
  onSelect: (slot: Availability) => void;
}) {
  const { t, formatTime } = useI18n();

  if (slots.length === 0) {
    return <p className="text-sm text-ink-muted">{t("booking.noTimes")}</p>;
  }

  return (
    <div className="grid grid-cols-2 gap-[9px] sm:grid-cols-3">
      {slots.map((slot) => {
        const isSelected = selectedSlot?.id === slot.id;
        return (
          <button
            key={slot.id}
            type="button"
            onClick={() => onSelect(slot)}
            aria-pressed={isSelected}
            className={cn(
              "rounded-field border p-3 text-sm font-medium transition-colors",
              isSelected ? "border-primary bg-primary text-white" : "border-border bg-surface text-ink hover:border-primary-line"
            )}
          >
            {formatTime(new Date(slot.start_time))}
          </button>
        );
      })}
    </div>
  );
}
