"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarClock } from "lucide-react";
import { ClinicShell } from "@/components/clinic/clinic-shell";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionTitle } from "@/components/ui/section-title";
import { useI18n } from "@/lib/i18n/provider";
import { fetchClinicSummary } from "@/services/clinic-service";
import { fetchAppointments } from "@/services/appointment-service";
import { LIVE } from "@/lib/query-options";
import type { MessageKey } from "@/lib/i18n/types";

const FIGURES: { key: "today" | "upcoming" | "pending" | "doctors" | "services" | "open_slots"; label: MessageKey }[] = [
  { key: "today", label: "clinic.today" },
  { key: "pending", label: "clinic.pendingConfirmation" },
  { key: "upcoming", label: "clinic.upcoming" },
  { key: "open_slots", label: "clinic.openSlots" },
  { key: "doctors", label: "clinic.countDoctors" },
  { key: "services", label: "clinic.countServices" },
];

/** Clinic dashboard overview (Sprint 13): the day's numbers and today's appointments. */
export default function ClinicOverviewPage() {
  const { t } = useI18n();
  return (
    <ClinicShell title={t("clinic.title")}>
      {(clinic) => <Overview clinicId={clinic.id} />}
    </ClinicShell>
  );
}

function Overview({ clinicId }: { clinicId: string }) {
  const { t, formatTime, label } = useI18n();
  const summary = useQuery({
    queryKey: ["clinic-summary", clinicId],
    queryFn: () => fetchClinicSummary(clinicId),
    ...LIVE,
  });
  const appointments = useQuery({
    queryKey: ["appointments", { clinic: clinicId }],
    queryFn: () => fetchAppointments({ clinic_id: clinicId, page_size: 100 }),
    ...LIVE,
  });

  const today = useMemo(() => {
    const now = new Date();
    return (appointments.data?.items ?? [])
      .filter((item) => {
        const start = new Date(item.scheduled_start);
        return start.toDateString() === now.toDateString() && item.status !== "cancelled";
      })
      .sort((a, b) => +new Date(a.scheduled_start) - +new Date(b.scheduled_start));
  }, [appointments.data]);

  return (
    <>
      {summary.isLoading ? (
        <Skeleton className="h-32" />
      ) : (
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
          {FIGURES.map(({ key, label: message }) => (
            <Card key={key} className="text-center">
              <p className="text-[26px] font-bold leading-none text-ink">{summary.data?.[key] ?? 0}</p>
              <p className="mt-1 text-xs text-ink-muted">{t(message)}</p>
            </Card>
          ))}
        </div>
      )}

      <SectionTitle title={t("clinic.todaySchedule")} href="/clinic/appointments" linkLabel={t("clinic.viewAll")} />
      {appointments.isLoading ? (
        <Skeleton className="h-32" />
      ) : today.length === 0 ? (
        <EmptyState icon={CalendarClock} title={t("clinic.noToday")} description={t("clinic.noTodayBody")} />
      ) : (
        <ul className="flex flex-col gap-2">
          {today.map((appointment) => (
            <li key={appointment.id}>
              <Card className="flex items-center justify-between gap-3 text-sm">
                <span className="font-bold text-ink">{formatTime(new Date(appointment.scheduled_start))}</span>
                <span className="text-xs text-ink-muted">{label("appointmentStatus", appointment.status)}</span>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
