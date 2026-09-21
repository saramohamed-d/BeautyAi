"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { SignInRequired } from "@/components/auth/sign-in-required";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import { fetchAdminOverview } from "@/services/admin-service";
import { LIVE } from "@/lib/query-options";
import { cn } from "@/lib/utils";
import type { MessageKey } from "@/lib/i18n/types";
import type { AdminOverview } from "@/types/admin";

const TABS: { href: string; label: MessageKey; badge?: keyof AdminOverview["attention"] }[] = [
  { href: "/admin", label: "admin.tabOverview" },
  { href: "/admin/verification", label: "admin.tabVerification", badge: "doctor_applications" },
  { href: "/admin/payments", label: "admin.tabPayments", badge: "needs_refund" },
  { href: "/admin/messages", label: "admin.tabMessages" },
  { href: "/admin/users", label: "admin.tabUsers" },
  { href: "/admin/audit", label: "admin.tabAudit" },
];

/** Shared frame for the platform admin screens (Sprint 14): access check, tabs, counts to act on. */
export function AdminShell({ children }: { children: (overview: AdminOverview | undefined) => ReactNode }) {
  const { t, formatNumber } = useI18n();
  const pathname = usePathname();
  const { status, user } = useAuth();
  const isAdmin = user?.role === "platform_admin";

  const overview = useQuery({ queryKey: ["admin-overview"], queryFn: fetchAdminOverview, enabled: isAdmin, ...LIVE });

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
        <PageHeader title={t("admin.title")} backHref="/" />
        <SignInRequired next="/admin" />
      </Page>
    );
  }
  if (!isAdmin) {
    return (
      <Page width="narrow">
        <PageHeader title={t("admin.title")} backHref="/" />
        <Card className="mt-8 text-center">
          <p className="font-bold text-ink">{t("admin.notAnAdmin")}</p>
          <LinkButton href="/" block className="mt-4">
            {t("confirmation.home")}
          </LinkButton>
        </Card>
      </Page>
    );
  }

  return (
    <Page width="wide">
      <PageHeader title={t("admin.title")} backHref="/" />
      <nav aria-label={t("admin.sections")} className="-mx-[18px] mt-1 flex gap-1.5 overflow-x-auto px-[18px] pb-1">
        {TABS.map((tab) => {
          const active = pathname === tab.href;
          const count = tab.badge ? (overview.data?.attention[tab.badge] ?? 0) : 0;
          return (
            <Link
              key={tab.href}
              href={tab.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-1.5 whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-bold transition-colors",
                active ? "border-primary bg-primary text-white" : "border-border bg-surface text-ink-muted hover:text-ink"
              )}
            >
              {t(tab.label)}
              {count > 0 && (
                <span
                  className={cn(
                    "rounded-full px-1.5 text-[10px]",
                    active ? "bg-white/25 text-white" : "bg-primary-soft text-primary-dark"
                  )}
                >
                  {formatNumber(count)}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="mt-4">{children(overview.data)}</div>
    </Page>
  );
}
