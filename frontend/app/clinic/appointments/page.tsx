"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock } from "lucide-react";
import { ClinicShell } from "@/components/clinic/clinic-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useI18n } from "@/lib/i18n/provider";
import { ApiError } from "@/lib/api-client";
import { cancelAppointment, fetchAppointments, updateAppointment } from "@/services/appointment-service";
import { fetchClinicStaff } from "@/services/clinic-service";
import { LIVE } from "@/lib/query-options";
import type { Appointment, AppointmentStatus } from "@/types/appointment";
import type { MessageKey } from "@/lib/i18n/types";

const FILTERS: { value: AppointmentStatus | "all"; label: MessageKey }[] = [
  { value: "all", label: "clinic.appointments.filterAll" },
  { value: "pending", label: "appointmentStatus.pending" },
  { value: "confirmed", label: "appointmentStatus.confirmed" },
  { value: "completed", label: "appointmentStatus.completed" },
  { value: "cancelled", label: "appointmentStatus.cancelled" },
];

const TONES: Record<AppointmentStatus, "primary" | "sage" | "neutral"> = {
  pending: "primary",
  confirmed: "sage",
  completed: "sage",
  cancelled: "neutral",
  no_show: "neutral",
};

/** Everything booked at this clinic, with the actions staff take on the day (Sprint 13). */
export default function ClinicAppointmentsPage() {
  const { t } = useI18n();
  return <ClinicShell title={t("clinic.title")}>{(clinic) => <Appointments clinicId={clinic.id} />}</ClinicShell>;
}

function Appointments({ clinicId }: { clinicId: string }) {
  const { t, formatDate, formatTime, label } = useI18n();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<AppointmentStatus | "all">("all");
  const [error, setError] = useState<string | null>(null);

  const appointments = useQuery({
    queryKey: ["appointments", { clinic: clinicId }],
    queryFn: () => fetchAppointments({ clinic_id: clinicId, page_size: 100 }),
    ...LIVE,
  });
  const staff = useQuery({ queryKey: ["clinic-staff", clinicId], queryFn: () => fetchClinicStaff(clinicId) });
  const doctorNameById = useMemo(
    () => new Map((staff.data ?? []).filter((m) => m.doctor_id).map((m) => [m.doctor_id as string, m.full_name])),
    [staff.data]
  );

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["appointments"] });
    queryClient.invalidateQueries({ queryKey: ["clinic-summary", clinicId] });
    queryClient.invalidateQueries({ queryKey: ["availability"] });
  };

  const change = useMutation({
    mutationFn: ({ id, status }: { id: string; status: AppointmentStatus }) =>
      status === "cancelled" ? cancelAppointment(id) : updateAppointment(id, { status }),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : t("errors.generic")),
  });

  const rows = useMemo(() => {
    const items = appointments.data?.items ?? [];
    return items
      .filter((item) => filter === "all" || item.status === filter)
      .sort((a, b) => +new Date(b.scheduled_start) - +new Date(a.scheduled_start));
  }, [appointments.data, filter]);

  return (
    <>
      <h2 className="text-lg font-bold text-ink">{t("clinic.appointments.title")}</h2>
      <p className="mt-1 text-sm text-ink-muted">{t("clinic.appointments.subtitle")}</p>

      <div className="-mx-[18px] mt-3 flex gap-1.5 overflow-x-auto px-[18px] pb-1" role="tablist">
        {FILTERS.map((option) => (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={filter === option.value}
            onClick={() => setFilter(option.value)}
            className={`whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-bold ${
              filter === option.value
                ? "border-primary bg-primary text-white"
                : "border-border bg-surface text-ink-muted"
            }`}
          >
            {t(option.label)}
          </button>
        ))}
      </div>

      {error && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {error}
        </p>
      )}

      {appointments.isLoading ? (
        <Skeleton className="mt-3 h-32" />
      ) : rows.length === 0 ? (
        <div className="mt-3">
          <EmptyState
            icon={CalendarClock}
            title={t("clinic.appointments.empty")}
            description={t("clinic.appointments.emptyBody")}
          />
        </div>
      ) : (
        <ul className="mt-3 flex flex-col gap-2">
          {rows.map((appointment) => (
            <li key={appointment.id}>
              <Card className="text-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-bold text-ink">
                      {formatDate(new Date(appointment.scheduled_start), "long")} ·{" "}
                      {formatTime(new Date(appointment.scheduled_start))}
                    </p>
                    <p className="mt-0.5 truncate text-xs text-ink-muted">
                      {doctorNameById.get(appointment.doctor_id) ?? ""}
                    </p>
                  </div>
                  <Badge tone={TONES[appointment.status]}>{label("appointmentStatus", appointment.status)}</Badge>
                </div>
                <Actions appointment={appointment} onChange={(status) => change.mutate({ id: appointment.id, status })} />
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function Actions({
  appointment,
  onChange,
}: {
  appointment: Appointment;
  onChange: (status: AppointmentStatus) => void;
}) {
  const { t } = useI18n();
  const started = new Date(appointment.scheduled_start) <= new Date();
  const actions: { status: AppointmentStatus; label: MessageKey; show: boolean }[] = ([
    { status: "confirmed", label: "clinic.appointments.confirm", show: appointment.status === "pending" },
    { status: "completed", label: "clinic.appointments.complete", show: appointment.status === "confirmed" && started },
    { status: "no_show", label: "clinic.appointments.noShow", show: appointment.status === "confirmed" && started },
    {
      status: "cancelled",
      label: "clinic.appointments.cancel",
      show: appointment.status === "pending" || appointment.status === "confirmed",
    },
  ] as { status: AppointmentStatus; label: MessageKey; show: boolean }[]).filter((action) => action.show);

  if (actions.length === 0) return null;

  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {actions.map((action) => (
        <Button
          key={action.status}
          variant="secondary"
          className="h-9 w-auto px-3 text-xs"
          onClick={() => {
            if (action.status === "cancelled" && !window.confirm(t("clinic.appointments.cancelConfirm"))) return;
            onChange(action.status);
          }}
        >
          {t(action.label)}
        </Button>
      ))}
    </div>
  );
}
