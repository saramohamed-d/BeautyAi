"use client";

import type { ReactNode } from "react";
import { CalendarClock, MapPin } from "lucide-react";
import { DoctorAvatar } from "@/components/doctors/doctor-avatar";
import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/lib/i18n/provider";
import type { Appointment, AppointmentStatus } from "@/types/appointment";

const STATUS_TONE: Record<AppointmentStatus, "primary" | "sage" | "neutral"> = {
  pending: "primary",
  confirmed: "sage",
  cancelled: "neutral",
  completed: "sage",
  no_show: "neutral",
};

export function AppointmentCard({
  appointment,
  doctorName,
  doctorAvatar,
  clinicName,
  footer,
}: {
  appointment: Appointment;
  doctorName: string;
  /** The doctor's illustrated avatar key, when known. */
  doctorAvatar?: string | null;
  clinicName: string;
  /** Optional actions shown under the details (e.g. cancel / reschedule). */
  footer?: ReactNode;
}) {
  const { label, formatDate, formatTime } = useI18n();
  const start = new Date(appointment.scheduled_start);

  return (
    <div className="rounded-card border border-border bg-surface p-3.5 shadow-card">
      <div className="flex items-center gap-[11px]">
        <DoctorAvatar avatar={doctorAvatar} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-bold text-ink">{doctorName}</p>
          <p className="mt-0.5 flex items-center gap-1 truncate text-xs text-ink-muted">
            <MapPin className="h-3 w-3 shrink-0" /> {clinicName}
          </p>
          <p className="mt-0.5 flex items-center gap-1 text-xs text-ink-muted">
            <CalendarClock className="h-3 w-3 shrink-0" /> {formatDate(start)} · {formatTime(start)}
          </p>
        </div>
        <Badge tone={STATUS_TONE[appointment.status]}>{label("appointmentStatus", appointment.status)}</Badge>
      </div>
      {footer && <div className="mt-3 border-t border-border pt-3">{footer}</div>}
    </div>
  );
}
