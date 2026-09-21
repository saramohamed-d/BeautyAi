"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { BadgeCheck, CalendarClock, Clock, XCircle } from "lucide-react";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionTitle } from "@/components/ui/section-title";
import { SignInRequired } from "@/components/auth/sign-in-required";
import { VerificationPanel } from "@/components/doctor/verification-panel";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import { fetchAppointments } from "@/services/appointment-service";
import { useClinics } from "@/hooks/use-clinics";
import type { Doctor } from "@/types/doctor";
import type { MessageKey } from "@/lib/i18n/types";

type Tone = "pending" | "review" | "verified" | "rejected";

function statusOf(doctor: Doctor): Tone {
  if (doctor.verification_status === "verified") return "verified";
  if (doctor.verification_status === "rejected") return "rejected";
  return doctor.submitted_at ? "review" : "pending";
}

const ICONS = { pending: Clock, review: Clock, verified: BadgeCheck, rejected: XCircle } as const;
const TITLES: Record<Tone, MessageKey> = {
  pending: "doctorDashboard.statusPending",
  review: "doctorDashboard.statusReview",
  verified: "doctorDashboard.statusVerified",
  rejected: "doctorDashboard.statusRejected",
};
const BODIES: Record<Tone, MessageKey> = {
  pending: "doctorDashboard.statusPendingBody",
  review: "doctorDashboard.statusReviewBody",
  verified: "doctorDashboard.statusVerifiedBody",
  rejected: "doctorDashboard.statusRejectedBody",
};
const STYLES: Record<Tone, string> = {
  pending: "bg-lavender-soft text-ink",
  review: "bg-lavender-soft text-ink",
  verified: "bg-sage-soft text-ink",
  rejected: "bg-red-50 text-ink",
};

/**
 * Doctor dashboard (Sprint 12; docs/verification.md).
 *
 * The first thing a doctor sees is where their application stands, and
 * what to do next: upload documents, submit, wait, or fix what the admin
 * rejected. Once verified, it shows their upcoming appointments.
 */
export default function DoctorDashboardPage() {
  const { t, formatDate, formatTime, label } = useI18n();
  const { status, user, doctor, refresh } = useAuth();

  const appointments = useQuery({
    queryKey: ["appointments", { doctor: doctor?.id }],
    queryFn: () => fetchAppointments({ page_size: 100 }),
    enabled: Boolean(doctor && doctor.verification_status === "verified"),
  });
  const { data: clinicsData } = useClinics({ page_size: 100 });
  const clinicNameById = useMemo(
    () => new Map(clinicsData?.items.map((clinic) => [clinic.id, clinic.name]) ?? []),
    [clinicsData]
  );

  const upcoming = useMemo(() => {
    const now = new Date();
    return (appointments.data?.items ?? [])
      .filter((item) => new Date(item.scheduled_start) >= now && item.status !== "cancelled")
      .sort((a, b) => +new Date(a.scheduled_start) - +new Date(b.scheduled_start))
      .slice(0, 5);
  }, [appointments.data]);

  if (status === "loading") {
    return (
      <Page width="narrow">
        <Skeleton className="mt-8 h-64" />
      </Page>
    );
  }
  if (!user) {
    return (
      <Page width="narrow">
        <PageHeader title={t("doctorDashboard.title")} backHref="/" />
        <SignInRequired next="/doctor" />
      </Page>
    );
  }
  if (!doctor) {
    // A logged-in patient or staff member who landed here by accident.
    return (
      <Page width="narrow">
        <PageHeader title={t("doctorDashboard.title")} backHref="/" />
        <Card className="mt-8 text-center">
          <p className="font-bold text-ink">{t("doctorDashboard.notADoctor")}</p>
          <LinkButton href="/signup/doctor" block className="mt-4">
            {t("doctorDashboard.joinCta")}
          </LinkButton>
        </Card>
      </Page>
    );
  }

  const tone = statusOf(doctor);
  const Icon = ICONS[tone];

  return (
    <Page width="narrow">
      <PageHeader title={t("doctorDashboard.title")} backHref="/" />
      <h2 className="text-[25px] font-bold leading-tight text-ink">
        {t("doctorDashboard.greeting", { name: doctor.full_name })}
      </h2>
      <p className="mt-1 text-sm text-ink-muted">{label("specialties", doctor.specialty)}</p>

      <div className={`mt-4 flex items-start gap-2.5 rounded-card p-[14px] ${STYLES[tone]}`} aria-live="polite">
        <Icon className="mt-0.5 h-5 w-5 shrink-0 text-primary-dark" aria-hidden="true" />
        <div className="text-sm">
          <p className="font-bold">{t(TITLES[tone])}</p>
          <p className="mt-0.5 leading-relaxed">{t(BODIES[tone])}</p>
          {tone === "rejected" && doctor.verification_notes && (
            <p className="mt-1.5 font-medium">
              {t("doctorDashboard.reason")}: {doctor.verification_notes}
            </p>
          )}
        </div>
      </div>

      {tone === "verified" ? (
        <section className="mt-6">
          <SectionTitle title={t("doctorDashboard.upcoming")} />
          {appointments.isLoading ? (
            <Skeleton className="mt-2 h-32" />
          ) : upcoming.length === 0 ? (
            <EmptyState
              icon={CalendarClock}
              title={t("doctorDashboard.noAppointments")}
              description={t("doctorDashboard.noAppointmentsBody")}
            />
          ) : (
            <ul className="mt-2 flex flex-col gap-2">
              {upcoming.map((appointment) => (
                <li key={appointment.id}>
                  <Card className="text-sm">
                    <p className="font-bold text-ink">
                      {formatDate(new Date(appointment.scheduled_start), "long")} ·{" "}
                      {formatTime(new Date(appointment.scheduled_start))}
                    </p>
                    <p className="mt-0.5 text-xs text-ink-muted">
                      {clinicNameById.get(appointment.clinic_id) ?? ""} · {label("appointmentStatus", appointment.status)}
                    </p>
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : (
        <VerificationPanel doctor={doctor} onSubmitted={refresh} />
      )}
    </Page>
  );
}
