"use client";

import { useMemo } from "react";
import Link from "next/link";
import { CalendarClock, MapPin, Stethoscope, User } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { usePatientContext } from "@/lib/patient-context";
import { useAppointments } from "@/hooks/use-appointments";
import { useDoctors } from "@/hooks/use-doctors";
import { useClinics } from "@/hooks/use-clinics";
import { formatDateArabic, formatTime } from "@/lib/format";
import type { Appointment, AppointmentStatus } from "@/types/appointment";

const STATUS_LABELS: Record<AppointmentStatus, string> = {
  pending: "قيد التأكيد",
  confirmed: "مؤكد",
  cancelled: "ملغي",
  completed: "مكتمل",
  no_show: "لم يحضر",
};

const STATUS_TONE: Record<AppointmentStatus, "primary" | "sage" | "neutral"> = {
  pending: "primary",
  confirmed: "sage",
  cancelled: "neutral",
  completed: "sage",
  no_show: "neutral",
};

function AppointmentRow({
  appointment,
  doctorName,
  clinicName,
}: {
  appointment: Appointment;
  doctorName: string;
  clinicName: string;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary-dark">
          <Stethoscope className="h-5 w-5" strokeWidth={1.75} />
        </div>
        <div>
          <p className="font-semibold text-ink">{doctorName}</p>
          <p className="flex items-center gap-1 text-sm text-ink-muted"><MapPin className="h-3.5 w-3.5" /> {clinicName}</p>
          <p className="mt-1 flex items-center gap-1.5 text-sm text-ink-muted">
            <CalendarClock className="h-3.5 w-3.5" />
            {formatDateArabic(new Date(appointment.scheduled_start))} — {formatTime(new Date(appointment.scheduled_start))}
          </p>
        </div>
      </div>
      <Badge tone={STATUS_TONE[appointment.status]}>{STATUS_LABELS[appointment.status]}</Badge>
    </div>
  );
}

export default function AppointmentsPage() {
  const { patient } = usePatientContext();
  const { data, isLoading, isError, refetch } = useAppointments({ patient_id: patient?.id, page_size: 100 });
  // Doctor/clinic names are looked up client-side from a bulk list rather
  // than one request per appointment, since Sprint 2 doesn't expose a
  // nested "appointment with doctor/clinic" response shape.
  const { data: doctorsData } = useDoctors({ page_size: 100 });
  const { data: clinicsData } = useClinics({ page_size: 100 });

  const doctorNameById = useMemo(
    () => new Map(doctorsData?.items.map((d) => [d.id, d.full_name]) ?? []),
    [doctorsData]
  );
  const clinicNameById = useMemo(
    () => new Map(clinicsData?.items.map((c) => [c.id, c.name]) ?? []),
    [clinicsData]
  );

  const { upcoming, previous } = useMemo(() => {
    const items = data?.items ?? [];
    const now = new Date();
    return {
      upcoming: items.filter((a) => new Date(a.scheduled_start) >= now).sort((a, b) => +new Date(a.scheduled_start) - +new Date(b.scheduled_start)),
      previous: items.filter((a) => new Date(a.scheduled_start) < now).sort((a, b) => +new Date(b.scheduled_start) - +new Date(a.scheduled_start)),
    };
  }, [data]);

  if (!patient) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center md:px-6">
        <User className="mx-auto h-10 w-10 text-ink-muted" strokeWidth={1.5} />
        <h1 className="mt-4 text-xl font-semibold text-ink">سجّلي الدخول لعرض مواعيدك</h1>
        <Link href="/login" className="mt-6 inline-block">
          <Button>تسجيل الدخول</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 md:px-6">
      <h1 className="text-2xl font-bold text-ink md:text-3xl">مواعيدي</h1>

      {isLoading && (
        <div className="mt-8 flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
        </div>
      )}

      {isError && <div className="mt-8"><ErrorState onRetry={() => refetch()} /></div>}

      {!isLoading && !isError && (
        <>
          <section className="mt-8">
            <h2 className="mb-4 text-lg font-semibold text-ink">المواعيد القادمة</h2>
            {upcoming.length === 0 ? (
              <EmptyState
                icon={CalendarClock}
                title="لا توجد مواعيد قادمة"
                description="احجزي موعدك القادم مع أحد أطبائنا الموثّقين."
                action={<Link href="/booking" className="mt-2"><Button size="sm">احجزي الآن</Button></Link>}
              />
            ) : (
              <div className="flex flex-col gap-3">
                {upcoming.map((a) => (
                  <AppointmentRow
                    key={a.id}
                    appointment={a}
                    doctorName={doctorNameById.get(a.doctor_id) ?? "—"}
                    clinicName={clinicNameById.get(a.clinic_id) ?? "—"}
                  />
                ))}
              </div>
            )}
          </section>

          {previous.length > 0 && (
            <section className="mt-10">
              <h2 className="mb-4 text-lg font-semibold text-ink">مواعيد سابقة</h2>
              <div className="flex flex-col gap-3">
                {previous.map((a) => (
                  <AppointmentRow
                    key={a.id}
                    appointment={a}
                    doctorName={doctorNameById.get(a.doctor_id) ?? "—"}
                    clinicName={clinicNameById.get(a.clinic_id) ?? "—"}
                  />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
