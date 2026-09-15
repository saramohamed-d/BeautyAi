"use client";

import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/format";
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
  if (slots.length === 0) {
    return <p className="text-sm text-ink-muted">لا توجد مواعيد متاحة في هذا اليوم. جرّبي يوماً آخر.</p>;
  }

  return (
    <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
      {slots.map((slot) => {
        const isSelected = selectedSlot?.id === slot.id;
        return (
          <button
            key={slot.id}
            type="button"
            onClick={() => onSelect(slot)}
            className={cn(
              "rounded-xl border px-3 py-2.5 text-sm font-medium transition-colors",
              isSelected ? "border-primary bg-primary text-white" : "border-border bg-surface text-ink hover:border-primary"
            )}
            aria-pressed={isSelected}
          >
            {formatTime(new Date(slot.start_time))}
          </button>
        );
      })}
    </div>
  );
}
