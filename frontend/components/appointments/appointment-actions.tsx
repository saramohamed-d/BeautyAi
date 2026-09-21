"use client";

import { useState } from "react";
import { Button, LinkButton } from "@/components/ui/button";
import { useCancelAppointment } from "@/hooks/use-appointment-actions";
import { useI18n } from "@/lib/i18n/provider";
import { ApiError } from "@/lib/api-client";
import type { Appointment } from "@/types/appointment";

const ACTIVE = new Set(["pending", "confirmed"]);

/** Whether the patient can still cancel/reschedule online (the clinic's cutoff, fixed at booking). */
export function canChangeOnline(appointment: Appointment, now = new Date()): boolean {
  const deadline = new Date(appointment.cancellable_until ?? appointment.scheduled_start);
  return ACTIVE.has(appointment.status) && now < deadline;
}

/**
 * Cancel / reschedule for a patient's upcoming appointment. Cancelling asks
 * for confirmation inline (no browser dialog, so it's translated and styled).
 * The server enforces the same cutoff; its answer wins if the clock drifted.
 */
export function AppointmentActions({ appointment }: { appointment: Appointment }) {
  const { t, formatDate, formatTime } = useI18n();
  const [confirming, setConfirming] = useState(false);
  const cancel = useCancelAppointment();

  if (!ACTIVE.has(appointment.status)) return null;

  const windowClosedByServer = cancel.error instanceof ApiError && cancel.error.code === "cancellation_window_closed";
  if (!canChangeOnline(appointment) || windowClosedByServer) {
    return <p className="text-xs text-ink-muted">{t("appointments.windowClosed")}</p>;
  }

  const deadline = new Date(appointment.cancellable_until ?? appointment.scheduled_start);

  if (confirming) {
    return (
      <div className="flex flex-col gap-2">
        <p className="text-sm font-semibold text-ink">{t("appointments.cancelConfirm")}</p>
        {cancel.isError && (
          <p role="alert" className="text-xs text-red-700">
            {t("appointments.actionFailed")}
          </p>
        )}
        <div className="flex gap-2">
          <Button
            size="sm"
            disabled={cancel.isPending}
            onClick={() => cancel.mutate({ id: appointment.id }, { onSuccess: () => setConfirming(false) })}
          >
            {t("appointments.cancelYes")}
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setConfirming(false)}>
            {t("appointments.keep")}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <span className="text-xs text-ink-muted">
        {t("appointments.changeUntil", { date: `${formatDate(deadline)} · ${formatTime(deadline)}` })}
      </span>
      <div className="flex gap-2">
        <LinkButton href={`/appointments/${appointment.id}/reschedule`} size="sm" variant="secondary">
          {t("appointments.reschedule")}
        </LinkButton>
        <Button size="sm" variant="ghost" onClick={() => setConfirming(true)}>
          {t("appointments.cancel")}
        </Button>
      </div>
    </div>
  );
}
