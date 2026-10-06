"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Building2, CalendarCheck } from "lucide-react";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { AppointmentCard } from "@/components/appointments/appointment-card";
import { canChangeOnline } from "@/components/appointments/appointment-actions";
import { BookingCalendar } from "@/components/booking/calendar";
import { TimeSlotGrid } from "@/components/booking/time-slot-grid";
import { SignInRequired } from "@/components/auth/sign-in-required";
import { Button, LinkButton } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Notice } from "@/components/ui/notice";
import { SelectableCard } from "@/components/ui/selectable-card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { useAppointment } from "@/hooks/use-appointment";
import { useAvailability } from "@/hooks/use-availability";
import { useDoctor } from "@/hooks/use-doctor";
import { useDoctorClinics } from "@/hooks/use-doctor-clinics";
import { useRescheduleAppointment } from "@/hooks/use-appointment-actions";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import { isSameDay, startOfDay } from "@/lib/format";
import { ApiError } from "@/lib/api-client";
import type { Availability } from "@/types/availability";

/**
 * Move an appointment to another open time with the same doctor, at any
 * of their clinics. The backend books the new slot and frees the old one
 * in one transaction; the appointment goes back to "pending" until the
 * clinic confirms.
 */
export default function ReschedulePage() {
  const { t } = useI18n();
  const params = useParams<{ id: string }>();
  const { status, patient } = useAuth();
  const { data: appointment, isLoading, isError, refetch } = useAppointment(patient ? params.id : undefined);
  const { data: doctor } = useDoctor(appointment?.doctor_id);
  const { clinics, isLoading: clinicsLoading } = useDoctorClinics(appointment?.doctor_id);

  const [clinicId, setClinicId] = useState<string | null>(null);
  const activeClinicId = clinicId ?? (clinics.some((c) => c.id === appointment?.clinic_id) ? appointment?.clinic_id : clinics[0]?.id);
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [slot, setSlot] = useState<Availability | null>(null);
  const reschedule = useRescheduleAppointment();

  const { data: slotsData, isLoading: slotsLoading } = useAvailability(
    { doctor_id: appointment?.doctor_id, clinic_id: activeClinicId ?? undefined, available: true, page_size: 100 },
    Boolean(appointment && activeClinicId)
  );
  const slots = (slotsData?.items ?? []).filter((s) => s.id !== appointment?.availability_id);
  const datesWithSlots = useMemo(() => slots.map((s) => startOfDay(new Date(s.start_time))), [slots]);
  const slotsForDate = selectedDate ? slots.filter((s) => isSameDay(new Date(s.start_time), selectedDate)) : [];

  const header = <PageHeader title={t("reschedule.title")} backHref="/appointments" />;

  if (status === "loading" || (patient && isLoading)) {
    return <Page width="narrow">{header}<Skeleton className="h-72" /></Page>;
  }
  if (!patient) {
    return <Page width="narrow">{header}<SignInRequired next={`/appointments/${params.id}/reschedule`} /></Page>;
  }
  if (isError || !appointment) {
    return <Page width="narrow">{header}<ErrorState onRetry={() => refetch()} /></Page>;
  }

  const clinicName = (id: string) => clinics.find((c) => c.id === id)?.name ?? "—";
  const errorCode = reschedule.error instanceof ApiError ? reschedule.error.code : undefined;

  if (reschedule.isSuccess) {
    return (
      <Page width="narrow">
        {header}
        <div className="mx-auto mb-3 mt-8 grid h-[72px] w-[72px] place-items-center rounded-full bg-primary-soft text-primary-dark">
          <CalendarCheck className="h-9 w-9" strokeWidth={1.75} />
        </div>
        <p className="mb-5 text-center text-sm text-ink">{t("reschedule.done")}</p>
        <AppointmentCard appointment={reschedule.data} doctorName={doctor?.full_name ?? "—"} doctorAvatar={doctor?.avatar} clinicName={clinicName(reschedule.data.clinic_id)} />
        <LinkButton href="/appointments" block className="mt-[15px]">
          {t("reschedule.back")}
        </LinkButton>
      </Page>
    );
  }

  const allowed = canChangeOnline(appointment) && errorCode !== "cancellation_window_closed";

  return (
    <Page width="narrow">
      {header}
      <p className="mb-2 text-sm font-bold text-ink">{t("reschedule.current")}</p>
      <AppointmentCard appointment={appointment} doctorName={doctor?.full_name ?? "—"} doctorAvatar={doctor?.avatar} clinicName={clinicName(appointment.clinic_id)} />

      {!allowed ? (
        <Notice className="mt-4">{errorCode === "cancellation_window_closed" ? t("appointments.windowClosed") : t("reschedule.notAllowed")}</Notice>
      ) : (
        <>
          <h2 className="mb-3 mt-6 text-[22px] font-bold text-ink">{t("reschedule.heading")}</h2>

          {clinicsLoading ? (
            <Skeleton className="h-16" />
          ) : (
            clinics.length > 1 && (
              <div className="mb-2.5 flex flex-col gap-2">
                <p className="text-sm font-bold text-ink">{t("reschedule.clinic")}</p>
                {clinics.map((clinic) => (
                  <SelectableCard
                    key={clinic.id}
                    selected={clinic.id === activeClinicId}
                    onClick={() => {
                      setClinicId(clinic.id);
                      setSelectedDate(null);
                      setSlot(null);
                    }}
                  >
                    <Building2 className="h-5 w-5 shrink-0 text-sage" strokeWidth={1.75} />
                    <span className="text-sm font-semibold text-ink">
                      {clinic.name} <span className="font-normal text-ink-muted">· {clinic.city}</span>
                    </span>
                  </SelectableCard>
                ))}
              </div>
            )
          )}

          <Card>
            <p className="mb-3 text-sm font-bold text-ink">{t("booking.date")}</p>
            {slotsLoading ? (
              <Skeleton className="h-16" />
            ) : (
              <BookingCalendar
                selectedDate={selectedDate}
                onSelect={(d) => {
                  setSelectedDate(d);
                  setSlot(null);
                }}
                datesWithSlots={datesWithSlots}
              />
            )}
          </Card>
          {selectedDate && (
            <div className="mt-2.5">
              <p className="mb-2 text-sm font-bold text-ink">{t("booking.times")}</p>
              <TimeSlotGrid slots={slotsForDate} selectedSlot={slot} onSelect={setSlot} />
            </div>
          )}

          {reschedule.isError && errorCode !== "cancellation_window_closed" && (
            <p role="alert" className="mt-3 text-sm text-red-700">
              {errorCode === "slot_unavailable" ? t("booking.taken") : t("appointments.actionFailed")}
            </p>
          )}
          <Button
            block
            className="mt-[15px]"
            disabled={!slot || reschedule.isPending}
            onClick={() => slot && reschedule.mutate({ id: appointment.id, availabilityId: slot.id })}
          >
            {reschedule.isPending ? t("reschedule.confirming") : t("reschedule.confirm")}
          </Button>
        </>
      )}
    </Page>
  );
}
