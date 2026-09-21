"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Building2, CalendarDays, ChevronRight, HeartPulse, Languages, ShieldCheck, Sparkles, Stethoscope, UserRound, type LucideIcon } from "lucide-react";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { LanguageToggle } from "@/components/layout/language-toggle";
import { AccountSecurity } from "@/components/account/account-security";
import { NotificationPreferences } from "@/components/account/notification-preferences";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button, LinkButton } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Notice } from "@/components/ui/notice";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import { withNext } from "@/lib/safe-next";
import type { MessageKey } from "@/lib/i18n/types";

const MENU: { href: string; icon: LucideIcon; label: MessageKey }[] = [
  { href: "/appointments", icon: CalendarDays, label: "profile.appointments" },
  { href: "/consultation", icon: Sparkles, label: "profile.consultations" },
];

const rowClass = "flex min-h-[52px] items-center gap-3 rounded-card border border-border bg-surface px-[14px] text-sm text-ink";

/**
 * Profile. Patients see their menu; doctors, clinic admins and platform
 * admins each get a link to their own dashboard (Sprints 12-14).
 */
export default function AccountPage() {
  const { t } = useI18n();
  const router = useRouter();
  const { status, user, patient, doctor, clinics, logout } = useAuth();

  const languageRow = (
    <div className={rowClass}>
      <Languages className="h-5 w-5 text-primary-dark" strokeWidth={1.75} />
      <span className="flex-1">{t("profile.language")}</span>
      <LanguageToggle />
    </div>
  );

  if (status === "loading") {
    return (
      <Page width="narrow">
        <PageHeader title={t("profile.title")} backHref="/" />
        <Skeleton className="h-72" />
      </Page>
    );
  }

  if (!user) {
    return (
      <Page width="narrow">
        <PageHeader title={t("profile.title")} backHref="/" />
        <EmptyState
          icon={UserRound}
          title={t("profile.guestTitle")}
          description={t("profile.guestBody")}
          action={
            <div className="flex flex-wrap justify-center gap-2">
              <LinkButton href={withNext("/login", "/account")} size="sm">{t("nav.signIn")}</LinkButton>
              <LinkButton href="/booking" size="sm" variant="secondary">{t("profile.book")}</LinkButton>
            </div>
          }
        />
        <div className="mt-2.5">{languageRow}</div>
      </Page>
    );
  }

  const displayName = patient?.full_name ?? user.email ?? user.phone ?? "";

  return (
    <Page width="narrow">
      <PageHeader title={t("profile.title")} backHref="/" />
      <div className="text-center">
        <Avatar name={displayName} size="lg" className="mx-auto my-6" />
        <h2 className="text-xl font-bold text-ink">{displayName}</h2>
        <p className="mt-1 text-xs text-ink-muted" dir="ltr">
          {user.email ?? user.phone}
        </p>
        {user.role !== "patient" && (
          <Badge tone="lavender" className="mt-2">
            {t("profile.role")}: {t(`roles.${user.role}`)}
          </Badge>
        )}
      </div>

      <div className="mt-5 flex flex-col gap-2.5">
        {patient ? (
          <>
            {MENU.map(({ href, icon: Icon, label }) => (
              <Link key={href} href={href} className={`${rowClass} hover:border-primary-line`}>
                <Icon className="h-5 w-5 text-primary-dark" strokeWidth={1.75} />
                <span className="flex-1">{t(label)}</span>
                <ChevronRight className="h-4 w-4 text-ink-muted rtl:rotate-180" />
              </Link>
            ))}
            <NotificationPreferences patient={patient} />
            <AccountSecurity user={user} />
            <div className={`${rowClass} opacity-70`} aria-disabled="true">
              <HeartPulse className="h-5 w-5 text-primary-dark" strokeWidth={1.75} />
              <span className="flex-1">{t("profile.history")}</span>
              <Badge tone="lavender">{t("common.soon")}</Badge>
            </div>
          </>
        ) : doctor ? (
          <Link href="/doctor" className={`${rowClass} hover:border-primary-line`}>
            <Stethoscope className="h-5 w-5 text-primary-dark" strokeWidth={1.75} />
            <span className="flex-1">{t("doctorDashboard.title")}</span>
            <ChevronRight className="h-4 w-4 text-ink-muted rtl:rotate-180" />
          </Link>
        ) : user.role === "platform_admin" ? (
          <Link href="/admin" className={`${rowClass} hover:border-primary-line`}>
            <ShieldCheck className="h-5 w-5 text-primary-dark" strokeWidth={1.75} />
            <span className="flex-1">{t("admin.title")}</span>
            <ChevronRight className="h-4 w-4 text-ink-muted rtl:rotate-180" />
          </Link>
        ) : clinics.length > 0 ? (
          <Link href="/clinic" className={`${rowClass} hover:border-primary-line`}>
            <Building2 className="h-5 w-5 text-primary-dark" strokeWidth={1.75} />
            <span className="flex-1">{t("clinic.title")}</span>
            <ChevronRight className="h-4 w-4 text-ink-muted rtl:rotate-180" />
          </Link>
        ) : (
          <Notice>{t("profile.staffNote")}</Notice>
        )}
        {languageRow}
      </div>

      <Button
        variant="secondary"
        block
        className="mt-[15px]"
        onClick={async () => {
          await logout();
          router.push("/login");
        }}
      >
        {t("profile.logout")}
      </Button>
    </Page>
  );
}
