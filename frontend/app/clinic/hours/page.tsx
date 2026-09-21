"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClinicShell } from "@/components/clinic/clinic-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/lib/i18n/provider";
import { fetchClinic, fetchClinicHours, saveClinicHours, updateClinic } from "@/services/clinic-service";
import type { ClinicHours } from "@/types/clinic";

// 0 = Monday … 6 = Sunday, shown Saturday-first as in Egypt.
const ORDER = [5, 6, 0, 1, 2, 3, 4];
const DEFAULT_DAY = { opens_at: "10:00:00", closes_at: "18:00:00" };

/** The clinic's weekly opening hours, used to publish bookable times (Sprint 13). */
export default function ClinicHoursPage() {
  const { t } = useI18n();
  return <ClinicShell title={t("clinic.title")}>{(clinic) => <Hours clinicId={clinic.id} />}</ClinicShell>;
}

function Hours({ clinicId }: { clinicId: string }) {
  const { t, formatWeekday } = useI18n();
  const queryClient = useQueryClient();
  const hours = useQuery({ queryKey: ["clinic-hours", clinicId], queryFn: () => fetchClinicHours(clinicId) });
  const clinic = useQuery({ queryKey: ["clinic", clinicId], queryFn: () => fetchClinic(clinicId) });
  const [days, setDays] = useState<Record<number, ClinicHours>>({});
  const [slotMinutes, setSlotMinutes] = useState("30");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!hours.data) return;
    const byWeekday: Record<number, ClinicHours> = {};
    for (const weekday of ORDER) {
      const existing = hours.data.find((day) => day.weekday === weekday);
      byWeekday[weekday] = existing ?? { weekday, ...DEFAULT_DAY, is_closed: true };
    }
    setDays(byWeekday);
  }, [hours.data]);

  useEffect(() => {
    if (clinic.data) setSlotMinutes(String(clinic.data.slot_duration_minutes));
  }, [clinic.data]);

  const save = useMutation({
    mutationFn: async () => {
      // Only the open days are sent; the rest are removed, which means closed.
      await saveClinicHours(
        clinicId,
        ORDER.map((weekday) => days[weekday]).filter((day): day is ClinicHours => day !== undefined && !day.is_closed)
      );
      await updateClinic(clinicId, { slot_duration_minutes: Number(slotMinutes) });
    },
    onSuccess: () => {
      setSaved(true);
      queryClient.invalidateQueries({ queryKey: ["clinic-hours", clinicId] });
      queryClient.invalidateQueries({ queryKey: ["clinic", clinicId] });
    },
  });

  function update(weekday: number, patch: Partial<ClinicHours>) {
    setSaved(false);
    setDays((prev) => {
      const current = prev[weekday];
      if (!current) return prev;
      return { ...prev, [weekday]: { ...current, ...patch } };
    });
  }

  // Monday 2024-01-01 was a Monday: used only to render weekday names.
  const weekdayName = (weekday: number) => formatWeekday(new Date(Date.UTC(2024, 0, 1 + weekday, 12)));
  const invalid = ORDER.some((weekday) => {
    const day = days[weekday];
    return day && !day.is_closed && day.closes_at <= day.opens_at;
  });

  if (hours.isLoading || clinic.isLoading) return <Skeleton className="h-64" />;

  return (
    <>
      <h2 className="text-lg font-bold text-ink">{t("clinic.hours.title")}</h2>
      <p className="mt-1 text-sm text-ink-muted">{t("clinic.hours.subtitle")}</p>

      <ul className="mt-3 flex flex-col gap-2">
        {ORDER.map((weekday) => {
          const day = days[weekday];
          if (!day) return null;
          return (
            <li key={weekday}>
              <Card className="text-sm">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-bold text-ink">{weekdayName(weekday)}</p>
                  <label className="flex items-center gap-2 text-xs text-ink-muted">
                    <input
                      type="checkbox"
                      aria-label={`${weekdayName(weekday)} — ${t("clinic.hours.open")}`}
                      className="h-4 w-4 accent-[color:var(--color-primary,#b34a63)]"
                      checked={!day.is_closed}
                      onChange={(event) => update(weekday, { is_closed: !event.target.checked })}
                    />
                    {day.is_closed ? t("clinic.hours.closed") : t("clinic.hours.open")}
                  </label>
                </div>
                {!day.is_closed && (
                  <div className="mt-2 flex items-end gap-2">
                    <Input
                      label={t("clinic.hours.from")}
                      type="time"
                      className="flex-1"
                      value={day.opens_at.slice(0, 5)}
                      onChange={(event) => update(weekday, { opens_at: `${event.target.value}:00` })}
                    />
                    <Input
                      label={t("clinic.hours.to")}
                      type="time"
                      className="flex-1"
                      value={day.closes_at.slice(0, 5)}
                      onChange={(event) => update(weekday, { closes_at: `${event.target.value}:00` })}
                    />
                  </div>
                )}
              </Card>
            </li>
          );
        })}
      </ul>

      <Card className="mt-3">
        <Input
          label={t("clinic.hours.slotLength")}
          type="number"
          inputMode="numeric"
          min={5}
          max={240}
          value={slotMinutes}
          onChange={(event) => {
            setSaved(false);
            setSlotMinutes(event.target.value);
          }}
        />
      </Card>

      {invalid && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {t("clinic.hours.invalid")}
        </p>
      )}
      <Button block className="mt-[15px]" disabled={invalid || save.isPending} onClick={() => save.mutate()}>
        {save.isPending ? t("clinic.saving") : t("clinic.hours.save")}
      </Button>
      {saved && !save.isPending && (
        <p className="mt-2 text-center text-xs text-ink-muted" aria-live="polite">
          {t("clinic.saved")}
        </p>
      )}
    </>
  );
}
