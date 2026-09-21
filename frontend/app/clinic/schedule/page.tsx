"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, X } from "lucide-react";
import { ClinicShell } from "@/components/clinic/clinic-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionTitle } from "@/components/ui/section-title";
import { useI18n } from "@/lib/i18n/provider";
import { ApiError } from "@/lib/api-client";
import { fetchAvailability } from "@/services/availability-service";
import { deleteSlot, fetchClinicStaff, generateSlots } from "@/services/clinic-service";
import type { Availability } from "@/types/availability";
import { LIVE } from "@/lib/query-options";

function isoDate(daysAhead = 0): string {
  const date = new Date();
  date.setDate(date.getDate() + daysAhead);
  return date.toISOString().slice(0, 10);
}

/** Turns the opening hours into bookable times for one doctor (Sprint 13). */
export default function ClinicSchedulePage() {
  const { t } = useI18n();
  return <ClinicShell title={t("clinic.title")}>{(clinic) => <Schedule clinicId={clinic.id} />}</ClinicShell>;
}

function Schedule({ clinicId }: { clinicId: string }) {
  const { t, formatDate, formatTime } = useI18n();
  const queryClient = useQueryClient();
  const [doctorId, setDoctorId] = useState("");
  const [from, setFrom] = useState(isoDate(1));
  const [to, setTo] = useState(isoDate(14));
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const staff = useQuery({ queryKey: ["clinic-staff", clinicId], queryFn: () => fetchClinicStaff(clinicId) });
  const doctors = (staff.data ?? []).filter((member) => member.role === "doctor" && member.doctor_id);

  const slots = useQuery({
    queryKey: ["availability", { clinic: clinicId, doctor: doctorId }],
    queryFn: () =>
      fetchAvailability({
        clinic_id: clinicId,
        ...(doctorId ? { doctor_id: doctorId } : {}),
        start_from: new Date().toISOString(),
        page_size: 100,
      }),
    ...LIVE,
  });

  // Grouped by day: a fortnight of half-hour slots is hundreds of rows otherwise.
  const byDay = useMemo(() => {
    const groups = new Map<string, Availability[]>();
    for (const slot of [...(slots.data?.items ?? [])].sort(
      (a, b) => +new Date(a.start_time) - +new Date(b.start_time)
    )) {
      const day = new Date(slot.start_time).toDateString();
      groups.set(day, [...(groups.get(day) ?? []), slot]);
    }
    return [...groups.entries()];
  }, [slots.data]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["availability"] });
    queryClient.invalidateQueries({ queryKey: ["clinic-summary", clinicId] });
  };

  const generate = useMutation({
    mutationFn: () => generateSlots(clinicId, { doctor_id: doctorId, date_from: from, date_to: to }),
    onSuccess: (result) => {
      setError(null);
      setMessage(
        t("clinic.schedule.result", { created: result.created, skipped: result.skipped_existing })
      );
      invalidate();
    },
    onError: (err) => {
      setMessage(null);
      if (err instanceof ApiError && err.code === "no_opening_hours") setError(t("clinic.schedule.noHours"));
      else if (err instanceof ApiError && err.code === "doctor_not_verified") setError(t("clinic.schedule.notVerified"));
      else if (err instanceof ApiError && err.status === 422) setError(t("clinic.schedule.tooLong"));
      else setError(t("errors.generic"));
    },
  });

  const remove = useMutation({
    mutationFn: (availabilityId: string) => deleteSlot(clinicId, availabilityId),
    onSuccess: invalidate,
    onError: (err) =>
      setError(err instanceof ApiError && err.code === "slot_booked" ? t("clinic.schedule.slotBooked") : t("errors.generic")),
  });

  return (
    <>
      <h2 className="text-lg font-bold text-ink">{t("clinic.schedule.title")}</h2>
      <p className="mt-1 text-sm text-ink-muted">{t("clinic.schedule.subtitle")}</p>

      <Card className="mt-3 flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-semibold text-ink-muted">{t("clinic.schedule.doctor")}</span>
          <select
            className="h-11 rounded-card border border-border bg-surface px-3 text-sm text-ink"
            value={doctorId}
            onChange={(event) => setDoctorId(event.target.value)}
          >
            <option value="">—</option>
            {doctors.map((member) => (
              <option key={member.id} value={member.doctor_id ?? ""}>
                {member.full_name}
              </option>
            ))}
          </select>
        </label>
        <div className="flex items-end gap-2">
          <Input
            label={t("clinic.schedule.from")}
            type="date"
            className="flex-1"
            value={from}
            onChange={(event) => setFrom(event.target.value)}
          />
          <Input
            label={t("clinic.schedule.to")}
            type="date"
            className="flex-1"
            value={to}
            onChange={(event) => setTo(event.target.value)}
          />
        </div>
        {doctors.length === 0 && <p className="text-xs text-ink-muted">{t("clinic.services.needsTeam")}</p>}
        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}
        {message && (
          <p className="text-sm text-ink" aria-live="polite">
            {message}
          </p>
        )}
        <Button block disabled={!doctorId || generate.isPending} onClick={() => generate.mutate()}>
          {generate.isPending ? t("clinic.schedule.generating") : t("clinic.schedule.generate")}
        </Button>
      </Card>

      <SectionTitle title={t("clinic.schedule.upcomingTitle")} />
      {slots.isLoading ? (
        <Skeleton className="h-32" />
      ) : byDay.length === 0 ? (
        <EmptyState
          icon={CalendarPlus}
          title={t("clinic.schedule.empty")}
          description={t("clinic.schedule.emptyBody")}
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {byDay.map(([day, daySlots]) => (
            <li key={day}>
              <Card>
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-bold text-ink">{formatDate(new Date(day), "long")}</p>
                  <span className="text-xs text-ink-muted">
                    {t("clinic.schedule.dayCount", { count: daySlots.length })}
                  </span>
                </div>
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {daySlots.map((slot) => (
                    <li key={slot.id}>
                      {slot.is_booked ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-sage-soft px-2.5 py-1 text-xs font-semibold text-ink">
                          {formatTime(new Date(slot.start_time))} · {t("clinic.schedule.booked")}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full border border-border bg-surface px-2.5 py-1 text-xs font-semibold text-ink-muted">
                          {formatTime(new Date(slot.start_time))}
                          <button
                            type="button"
                            aria-label={`${t("clinic.schedule.removeSlot")} ${formatTime(new Date(slot.start_time))}`}
                            className="text-ink-muted hover:text-red-700"
                            onClick={() => remove.mutate(slot.id)}
                          >
                            <X className="h-3 w-3" aria-hidden="true" />
                          </button>
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
