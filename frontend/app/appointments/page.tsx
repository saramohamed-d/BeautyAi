"use client";

import { useMemo, useState } from "react";
import { CalendarClock, CalendarDays, Sparkles, UserRound, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { AppointmentCard } from "@/components/appointments/appointment-card";
import { AppointmentActions } from "@/components/appointments/appointment-actions";
import { LinkButton } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/types";
import { cn } from "@/lib/utils";
import { withNext } from "@/lib/safe-next";
import { useAppointments } from "@/hooks/use-appointments";
import { useDoctors } from "@/hooks/use-doctors";
import { useClinics } from "@/hooks/use-clinics";

type Tab = "upcoming" | "past" | "cancelled";
const TABS: { key: Tab; label: MessageKey }[] = [
  { key: "upcoming", label: "appointments.upcoming" },
  { key: "past", label: "appointments.past" },
  { key: "cancelled", label: "appointments.cancelled" },
];

const MENU: { href: string; label: MessageKey; icon: LucideIcon }[] = [
  { href: "/appointments", label: "nav.appointments", icon: CalendarDays },
  { href: "/consultation", label: "profile.consultations", icon: Sparkles },
  { href: "/account", label: "nav.profile", icon: UserRound },
];

/** Desktop-only side menu of the patient's own pages (the mock-up's "My Appointments" layout). */
function PatientMenu() {
  const { t } = useI18n();
  return (
    <nav aria-label={t("appointments.menu")} className="hidden w-52 shrink-0 md:block">
      <ul className="sticky top-24 flex flex-col gap-1 rounded-card border border-border bg-surface p-2 shadow-card">
        {MENU.map(({ href, label, icon: Icon }) => {
          const active = href === "/appointments";
          return (
            <li key={href}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium",
                  active ? "bg-primary-soft font-bold text-primary-dark" : "text-ink hover:bg-bg"
                )}
              >
                <Icon className="h-4 w-4" strokeWidth={1.75} /> {t(label)}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export default function AppointmentsPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("upcoming");
  const { status, patient } = useAuth();
  const { data, isLoading, isError, refetch } = useAppointments({ patient_id: patient?.id, page_size: 100 });
  // Names come from bulk lists rather than one request per appointment:
  // the API has no nested "appointment with doctor/clinic" response yet.
  const { data: doctorsData } = useDoctors({ page_size: 100 });
  const { data: clinicsData } = useClinics({ page_size: 100 });

  const doctorById = useMemo(() => new Map(doctorsData?.items.map((d) => [d.id, d]) ?? []), [doctorsData]);
  const clinicNameById = useMemo(() => new Map(clinicsData?.items.map((c) => [c.id, c.name]) ?? []), [clinicsData]);

  const lists = useMemo(() => {
    const items = data?.items ?? [];
    const now = new Date();
    const active = items.filter((a) => a.status !== "cancelled");
    return {
      upcoming: active
        .filter((a) => new Date(a.scheduled_start) >= now)
        .sort((a, b) => +new Date(a.scheduled_start) - +new Date(b.scheduled_start)),
      past: active
        .filter((a) => new Date(a.scheduled_start) < now)
        .sort((a, b) => +new Date(b.scheduled_start) - +new Date(a.scheduled_start)),
      cancelled: items
        .filter((a) => a.status === "cancelled")
        .sort((a, b) => +new Date(b.scheduled_start) - +new Date(a.scheduled_start)),
    };
  }, [data]);
  const shown = lists[tab];

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

  const card = (a: (typeof shown)[number], withActions = false) => (
    <AppointmentCard
      key={a.id}
      appointment={a}
      doctorName={doctorById.get(a.doctor_id)?.full_name ?? "—"}
      doctorAvatar={doctorById.get(a.doctor_id)?.avatar}
      clinicName={clinicNameById.get(a.clinic_id) ?? "—"}
      footer={withActions && (a.status === "pending" || a.status === "confirmed") ? <AppointmentActions appointment={a} /> : undefined}
    />
  );

  return (
    <Page>
      <div className="flex gap-8">
        <PatientMenu />
        <div className="min-w-0 flex-1 md:max-w-2xl">
          <h1 className="font-display text-[28px] font-semibold text-ink md:text-4xl">{t("appointments.title")}</h1>

          <div role="tablist" aria-label={t("appointments.title")} className="mt-4 flex gap-1 border-b border-border">
            {TABS.map(({ key, label }) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={tab === key}
                onClick={() => setTab(key)}
                className={cn(
                  "-mb-px border-b-2 px-4 py-2.5 text-sm font-semibold transition-colors",
                  tab === key ? "border-primary text-primary-dark" : "border-transparent text-ink-muted hover:text-ink"
                )}
              >
                {t(label)}
                {lists[key].length > 0 && <span className="ms-1.5 text-xs text-ink-muted">({lists[key].length})</span>}
              </button>
            ))}
          </div>

          <div className="mt-4">
            {isLoading && (
              <div className="flex flex-col gap-2.5">
                {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-[84px]" />)}
              </div>
            )}

            {isError && <ErrorState onRetry={() => refetch()} />}

            {!isLoading && !isError && shown.length === 0 && (
              <EmptyState
                icon={CalendarClock}
                title={t(tab === "upcoming" ? "appointments.emptyTitle" : "appointments.emptyOther")}
                description={tab === "upcoming" ? t("appointments.emptyBody") : undefined}
                action={tab === "upcoming" ? <LinkButton href="/doctors" size="sm">{t("appointments.bookNow")}</LinkButton> : undefined}
              />
            )}

            {!isLoading && !isError && shown.length > 0 && (
              <div className="flex flex-col gap-2.5">{shown.map((a) => card(a, tab === "upcoming"))}</div>
            )}
          </div>
        </div>
      </div>
    </Page>
  );
}
