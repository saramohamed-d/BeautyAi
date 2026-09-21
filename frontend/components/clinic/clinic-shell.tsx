"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { SignInRequired } from "@/components/auth/sign-in-required";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import { useSelectedClinic } from "@/hooks/use-selected-clinic";
import { cn } from "@/lib/utils";
import type { ClinicMembership } from "@/types/clinic";
import type { MessageKey } from "@/lib/i18n/types";

const TABS: { href: string; label: MessageKey }[] = [
  { href: "/clinic", label: "clinic.tabOverview" },
  { href: "/clinic/appointments", label: "clinic.tabAppointments" },
  { href: "/clinic/schedule", label: "clinic.tabSchedule" },
  { href: "/clinic/team", label: "clinic.tabTeam" },
  { href: "/clinic/services", label: "clinic.tabServices" },
  { href: "/clinic/hours", label: "clinic.tabHours" },
];

/**
 * Frame shared by every clinic admin screen (Sprint 13): the sign-in and
 * role checks, which clinic is being managed, and the section tabs.
 *
 * The children get the selected clinic, so each screen only deals with
 * its own data.
 */
export function ClinicShell({
  title,
  children,
}: {
  title: string;
  children: (clinic: ClinicMembership) => ReactNode;
}) {
  const { t } = useI18n();
  const pathname = usePathname();
  const { status, user } = useAuth();
  const { clinics, clinic, selectClinic } = useSelectedClinic();

  if (status === "loading") {
    return (
      <Page width="wide">
        <Skeleton className="mt-8 h-64" />
      </Page>
    );
  }
  if (!user) {
    return (
      <Page width="narrow">
        <PageHeader title={t("clinic.title")} backHref="/" />
        <SignInRequired next="/clinic" />
      </Page>
    );
  }
  if (clinics.length === 0) {
    // A logged-in patient or doctor who opened the clinic dashboard.
    return (
      <Page width="narrow">
        <PageHeader title={t("clinic.title")} backHref="/" />
        <Card className="mt-8 text-center">
          <p className="font-bold text-ink">{t("clinic.noClinics")}</p>
          <p className="mt-1 text-sm text-ink-muted">{t("clinic.noClinicsBody")}</p>
          <LinkButton href="/" block className="mt-4">
            {t("confirmation.home")}
          </LinkButton>
        </Card>
      </Page>
    );
  }

  return (
    <Page width="wide">
      <PageHeader title={title} backHref="/" />

      {clinics.length > 1 ? (
        <label className="mt-1 flex flex-col gap-1 text-sm">
          <span className="font-semibold text-ink-muted">{t("clinic.managing")}</span>
          <select
            className="h-11 rounded-card border border-border bg-surface px-3 text-sm font-bold text-ink"
            value={clinic?.id ?? ""}
            onChange={(event) => selectClinic(event.target.value)}
          >
            {clinics.map((option) => (
              <option key={option.id} value={option.id}>
                {option.name}
              </option>
            ))}
          </select>
        </label>
      ) : (
        clinic && <p className="text-sm text-ink-muted">{clinic.name}</p>
      )}

      <nav aria-label={t("clinic.sections")} className="-mx-[18px] mt-3 flex gap-1.5 overflow-x-auto px-[18px] pb-1">
        {TABS.map((tab) => {
          const active = pathname === tab.href;
          return (
            <Link
              key={tab.href}
              href={tab.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-bold transition-colors",
                active
                  ? "border-primary bg-primary text-white"
                  : "border-border bg-surface text-ink-muted hover:text-ink"
              )}
            >
              {t(tab.label)}
            </Link>
          );
        })}
      </nav>

      <div className="mt-4">{clinic ? children(clinic) : <Skeleton className="h-48" />}</div>
    </Page>
  );
}
