"use client";

import { isSameDay, nextDays } from "@/lib/format";
import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

/**
 * A horizontal 14-day date strip rather than a full month grid: people
 * booking a consultation almost always want "soon". Days without open
 * slots are disabled so the picker never leads into a dead end.
 */
export function BookingCalendar({
  selectedDate,
  onSelect,
  datesWithSlots,
}: {
  selectedDate: Date | null;
  onSelect: (date: Date) => void;
  datesWithSlots: Date[];
}) {
  const { formatWeekday, formatNumber, formatDate } = useI18n();
  const days = nextDays(14);

  return (
    <div className="no-scrollbar -mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
      {days.map((day) => {
        const hasSlots = datesWithSlots.some((d) => isSameDay(d, day));
        const isSelected = Boolean(selectedDate && isSameDay(selectedDate, day));
        return (
          <button
            key={day.toISOString()}
            type="button"
            disabled={!hasSlots}
            onClick={() => onSelect(day)}
            aria-pressed={isSelected}
            aria-label={formatDate(day, "long")}
            className={cn(
              "flex w-[52px] shrink-0 flex-col items-center gap-0.5 rounded-[11px] py-2 transition-colors",
              isSelected ? "bg-primary text-white" : "bg-surface text-ink hover:bg-primary-soft",
              !hasSlots && "cursor-not-allowed opacity-35 hover:bg-surface"
            )}
          >
            <span className={cn("text-[11px]", isSelected ? "text-white/90" : "text-ink-muted")}>{formatWeekday(day)}</span>
            <span className="text-base font-bold">{formatNumber(day.getDate())}</span>
          </button>
        );
      })}
    </div>
  );
}
