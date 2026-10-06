"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BadgeCheck, CalendarClock, CalendarDays, Clock, MapPin, Pencil, Sun, XCircle } from "lucide-react";
import { Page } from "@/components/layout/page";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button, LinkButton } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionTitle } from "@/components/ui/section-title";
import { SignInRequired } from "@/components/auth/sign-in-required";
import { VerificationPanel } from "@/components/doctor/verification-panel";
import { DoctorAvatar } from "@/components/doctors/doctor-avatar";
import { AvatarPicker } from "@/components/doctors/avatar-picker";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import { fetchAppointments } from "@/services/appointment-service";
import { updateDoctor } from "@/services/doctor-service";
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

function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/** The doctor's own picture: shows the avatar, and lets them pick another. */
function AvatarCard({ doctor, onSaved }: { doctor: Doctor; onSaved: () => Promise<void> }) {
  const { t, label } = useI18n();
  const [editing, setEditing] = useState(false);
  const [choice, setChoice] = useState(doctor.avatar ?? null);
  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(false);

  async function save() {
    if (!choice) return;
    setSaving(true);
    setFailed(false);
    try {
      await updateDoctor(doctor.id, { avatar: choice });
      await onSaved();
      setEditing(false);
    } catch {
      setFailed(true);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="bg-gradient-to-br from-blush to-surface p-5">
      <div className="flex items-center gap-4">
        <DoctorAvatar avatar={doctor.avatar} size="lg" />
        <div className="min-w-0 flex-1">
          <p className="text-xs text-ink-muted">{t("doctorDashboard.welcome")}</p>
          <h1 className="truncate font-display text-2xl font-semibold text-ink">{doctor.full_name}</h1>
          <p className="text-sm text-ink-muted">{label("specialties", doctor.specialty)}</p>
        </div>
        {!editing && (
          <Button size="sm" variant="secondary" onClick={() => setEditing(true)} className="shrink-0">
            <Pencil className="h-3.5 w-3.5" /> {t("avatar.change")}
          </Button>
        )}
      </div>
      {editing && (
        <div className="mt-4 border-t border-primary-line/50 pt-4">
          <AvatarPicker value={choice} onChange={setChoice} />
          {failed && (
            <p role="alert" className="mt-2 text-sm text-red-700">
              {t("errors.generic")}
            </p>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              {t("avatar.cancel")}
            </Button>
            <Button size="sm" onClick={save} disabled={!choice || saving}>
              {t("avatar.save")}
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

/**
 * Doctor dashboard (Sprint 12; docs/verification.md).
 *
 * Only the doctor's own things: their profile picture, where their
 * application stands (upload documents, submit, wait, or fix what the
 * admin rejected) and, once verified, their own appointments. Doctors
 * never see the patient side of the app (other doctors, booking).
 */
export default function DoctorDashboardPage() {
  const { t, formatDate, formatTime, formatWeekday, formatNumber, label } = useI18n();
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

  const { upcoming, today, week } = useMemo(() => {
    const now = new Date();
    const inAWeek = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
    const items = (appointments.data?.items ?? [])
      .filter((item) => new Date(item.scheduled_start) >= now && item.status !== "cancelled")
      .sort((a, b) => +new Date(a.scheduled_start) - +new Date(b.scheduled_start));
    return {
      upcoming: items,
      today: items.filter((item) => sameDay(new Date(item.scheduled_start), now)).length,
      week: items.filter((item) => new Date(item.scheduled_start) <= inAWeek).length,
    };
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
        <SignInRequired next="/doctor" />
      </Page>
    );
  }
  if (!doctor) {
    // A logged-in patient or staff member who landed here by accident.
    return (
      <Page width="narrow">
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
  const stats = [
    { icon: Sun, label: t("doctorDashboard.statToday"), value: today },
    { icon: CalendarDays, label: t("doctorDashboard.statWeek"), value: week },
    { icon: CalendarClock, label: t("doctorDashboard.statUpcoming"), value: upcoming.length },
  ];

  return (
    <Page width="narrow">
      <AvatarCard doctor={doctor} onSaved={refresh} />

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
        <>
          <div className="mt-4 grid grid-cols-3 gap-2.5">
            {stats.map(({ icon: StatIcon, label: statLabel, value }) => (
              <Card key={statLabel} className="text-center">
                <StatIcon className="mx-auto h-5 w-5 text-primary" strokeWidth={1.75} aria-hidden="true" />
                <p className="mt-1.5 text-2xl font-bold text-ink">{appointments.isLoading ? "–" : formatNumber(value)}</p>
                <p className="text-[11px] text-ink-muted">{statLabel}</p>
              </Card>
            ))}
          </div>

          <section className="mt-2">
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
              <ul className="flex flex-col gap-2">
                {upcoming.slice(0, 10).map((appointment) => {
                  const start = new Date(appointment.scheduled_start);
                  return (
                    <li key={appointment.id}>
                      <Card className="flex items-center gap-3">
                        <div className="flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-xl bg-primary-soft text-primary-dark">
                          <span className="text-[10px] font-semibold uppercase leading-none">{formatWeekday(start)}</span>
                          <span className="mt-0.5 text-lg font-bold leading-none">{formatNumber(start.getDate())}</span>
                        </div>
                        <div className="min-w-0 flex-1 text-sm">
                          <p className="font-bold text-ink">
                            {formatDate(start, "long")} · {formatTime(start)}
                          </p>
                          <p className="mt-0.5 flex items-center gap-1 truncate text-xs text-ink-muted">
                            <MapPin className="h-3 w-3 shrink-0" /> {clinicNameById.get(appointment.clinic_id) ?? ""}
                          </p>
                        </div>
                        <Badge tone={appointment.status === "confirmed" ? "sage" : "primary"}>
                          {label("appointmentStatus", appointment.status)}
                        </Badge>
                      </Card>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </>
      ) : (
        <VerificationPanel doctor={doctor} onSubmitted={refresh} />
      )}
    </Page>
  );
}
