"use client";

import { useMemo } from "react";
import { CalendarClock, UserRound } from "lucide-react";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { AppointmentCard } from "@/components/appointments/appointment-card";
import { AppointmentActions } from "@/components/appointments/appointment-actions";
import { LinkButton } from "@/components/ui/button";
import { SectionTitle } from "@/components/ui/section-title";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import { withNext } from "@/lib/safe-next";
import { useAppointments } from "@/hooks/use-appointments";
import { useDoctors } from "@/hooks/use-doctors";
import { useClinics } from "@/hooks/use-clinics";

export default function AppointmentsPage() {
  const { t } = useI18n();
  const { status, patient } = useAuth();
  const { data, isLoading, isError, refetch } = useAppointments({ patient_id: patient?.id, page_size: 100 });
  // Names come from bulk lists rather than one request per appointment:
  // the API has no nested "appointment with doctor/clinic" response yet.
  const { data: doctorsData } = useDoctors({ page_size: 100 });
  const { data: clinicsData } = useClinics({ page_size: 100 });

  const doctorNameById = useMemo(() => new Map(doctorsData?.items.map((d) => [d.id, d.full_name]) ?? []), [doctorsData]);
  const clinicNameById = useMemo(() => new Map(clinicsData?.items.map((c) => [c.id, c.name]) ?? []), [clinicsData]);

  const { upcoming, past } = useMemo(() => {
    const items = data?.items ?? [];
    const now = new Date();
    return {
      upcoming: items
        .filter((a) => new Date(a.scheduled_start) >= now)
        .sort((a, b) => +new Date(a.scheduled_start) - +new Date(b.scheduled_start)),
      past: items
        .filter((a) => new Date(a.scheduled_start) < now)
        .sort((a, b) => +new Date(b.scheduled_start) - +new Date(a.scheduled_start)),
    };
  }, [data]);

  if (status === "loading") {
    return (
      <Page width="narrow">
        <PageHeader title={t("appointments.title")} backHref="/" />
        <Skeleton className="h-[76px]" />
      </Page>
    );
  }

  if (!patient) {
    return (
      <Page width="narrow">
        <PageHeader title={t("appointments.title")} backHref="/" />
        <EmptyState
          icon={UserRound}
          title={t("appointments.signInTitle")}
          action={<LinkButton href={withNext("/login", "/appointments")} size="sm">{t("nav.signIn")}</LinkButton>}
        />
      </Page>
    );
  }

  const card = (a: (typeof upcoming)[number], withActions = false) => (
    <AppointmentCard
      key={a.id}
      appointment={a}
      doctorName={doctorNameById.get(a.doctor_id) ?? "—"}
      clinicName={clinicNameById.get(a.clinic_id) ?? "—"}
      footer={withActions && (a.status === "pending" || a.status === "confirmed") ? <AppointmentActions appointment={a} /> : undefined}
    />
  );

  return (
    <Page width="narrow">
      <PageHeader title={t("appointments.title")} backHref="/" />

      {isLoading && (
        <div className="flex flex-col gap-2.5">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-[76px]" />)}
        </div>
      )}

      {isError && <ErrorState onRetry={() => refetch()} />}

      {!isLoading && !isError && (
        <>
          <SectionTitle title={t("appointments.upcoming")} />
          {upcoming.length === 0 ? (
            <EmptyState
              icon={CalendarClock}
              title={t("appointments.emptyTitle")}
              description={t("appointments.emptyBody")}
              action={<LinkButton href="/booking" size="sm">{t("appointments.bookNow")}</LinkButton>}
            />
          ) : (
            <div className="flex flex-col gap-2.5">{upcoming.map((a) => card(a, true))}</div>
          )}

          {past.length > 0 && (
            <>
              <SectionTitle title={t("appointments.past")} />
              <div className="flex flex-col gap-2.5">{past.map((a) => card(a))}</div>
            </>
          )}
        </>
      )}
    </Page>
  );
}
