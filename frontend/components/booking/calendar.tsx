"use client";

import { cn } from "@/lib/utils";
import { formatDateArabic, isSameDay, nextDays, weekdayShortArabic } from "@/lib/format";

/**
 * A horizontal 14-day date strip rather than a full month grid.
 *
 * Design decision: patients booking a beauty/dermatology appointment
 * almost always want "soon" — a two-week strip surfaces real availability
 * at a glance without the extra taps of a month calendar with mostly
 * irrelevant past/far-future dates. `datesWithSlots` (derived from the
 * doctor+clinic's actual availability) dims days with nothing bookable,
 * so the picker never leads someone into a dead end.
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
  const days = nextDays(14);

  return (
    <div className="flex gap-2 overflow-x-auto pb-2">
      {days.map((day) => {
        const hasSlots = datesWithSlots.some((d) => isSameDay(d, day));
        const isSelected = selectedDate && isSameDay(selectedDate, day);
        return (
          <button
            key={day.toISOString()}
            type="button"
            disabled={!hasSlots}
            onClick={() => onSelect(day)}
            className={cn(
              "flex w-20 shrink-0 flex-col items-center gap-1 rounded-2xl border px-3 py-3 text-center transition-colors",
              isSelected ? "border-primary bg-primary text-white" : "border-border bg-surface text-ink",
              !hasSlots && "cursor-not-allowed opacity-40"
            )}
            aria-pressed={Boolean(isSelected)}
          >
            <span className="text-xs">{weekdayShortArabic(day)}</span>
            <span className="text-lg font-semibold">{day.getDate()}</span>
          </button>
        );
      })}
      {selectedDate && (
        <p className="sr-only">التاريخ المحدد: {formatDateArabic(selectedDate)}</p>
      )}
    </div>
  );
}
