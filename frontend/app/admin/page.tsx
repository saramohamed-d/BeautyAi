"use client";

import Link from "next/link";
import { AlertCircle, CheckCircle2 } from "lucide-react";
import { AdminShell } from "@/components/admin/admin-shell";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { SectionTitle } from "@/components/ui/section-title";
import { useI18n } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/types";
import type { AdminOverview } from "@/types/admin";

const ATTENTION: { key: keyof AdminOverview["attention"]; label: MessageKey; href: string }[] = [
  { key: "doctor_applications", label: "admin.applications", href: "/admin/verification" },
  { key: "needs_refund", label: "admin.needsRefund", href: "/admin/payments" },
  { key: "safety_events", label: "admin.safetyEvents", href: "/admin/audit" },
  { key: "knowledge_review", label: "admin.knowledgeReview", href: "/admin/audit" },
];

/** Platform overview (Sprint 14): what needs a human, then the figures. */
export default function AdminOverviewPage() {
  return <AdminShell>{(overview) => <Overview overview={overview} />}</AdminShell>;
}

function Overview({ overview }: { overview: AdminOverview | undefined }) {
  const { t, formatNumber, formatCurrency } = useI18n();
  if (!overview) return <Skeleton className="h-64" />;

  const waiting = ATTENTION.filter(({ key }) => overview.attention[key] > 0);
  const maxBookings = Math.max(1, ...overview.daily.map((point) => point.bookings));

  const figures: { label: MessageKey; value: string }[] = [
    { label: "admin.totalUsers", value: formatNumber(overview.users.total) },
    { label: "admin.newThisMonth", value: formatNumber(overview.users.new_this_month) },
    { label: "admin.suspended", value: formatNumber(overview.users.suspended) },
    { label: "admin.activeClinics", value: formatNumber(overview.clinics.active) },
    { label: "admin.upcoming", value: formatNumber(overview.appointments.upcoming) },
    { label: "admin.dueAtClinic", value: formatNumber(overview.payments.due_at_clinic) },
  ];

  return (
    <>
      <SectionTitle title={t("admin.attention")} />
      {waiting.length === 0 ? (
        <Card className="flex items-center gap-2 text-sm">
          <CheckCircle2 className="h-5 w-5 text-primary-dark" aria-hidden="true" />
          {t("admin.attentionNone")}
        </Card>
      ) : (
        <ul className="flex flex-col gap-2">
          {waiting.map(({ key, label, href }) => (
            <li key={key}>
              <Link href={href}>
                <Card className="flex items-center justify-between gap-3 text-sm hover:border-primary-line">
                  <span className="flex items-center gap-2 font-bold text-ink">
                    <AlertCircle className="h-4 w-4 text-primary-dark" aria-hidden="true" />
                    {t(label)}
                  </span>
                  <span className="rounded-full bg-primary-soft px-2 py-0.5 text-xs font-bold text-primary-dark">
                    {formatNumber(overview.attention[key])}
                  </span>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}

      <SectionTitle title={t("admin.money")} />
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
        <Card className="text-center">
          <p className="text-[22px] font-bold leading-none text-ink">{formatCurrency(overview.payments.paid_total)}</p>
          <p className="mt-1 text-xs text-ink-muted">{t("admin.paidTotal")}</p>
        </Card>
        <Card className="text-center">
          <p className="text-[22px] font-bold leading-none text-ink">
            {formatCurrency(overview.payments.paid_this_month)}
          </p>
          <p className="mt-1 text-xs text-ink-muted">{t("admin.paidThisMonth")}</p>
        </Card>
        <Card className="text-center">
          <p className="text-[22px] font-bold leading-none text-ink">
            {formatCurrency(overview.payments.refunded_total)}
          </p>
          <p className="mt-1 text-xs text-ink-muted">{t("admin.refundedTotal")}</p>
        </Card>
      </div>

      <SectionTitle title={t("admin.people")} />
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
        {figures.map(({ label, value }) => (
          <Card key={label} className="text-center">
            <p className="text-[22px] font-bold leading-none text-ink">{value}</p>
            <p className="mt-1 text-xs text-ink-muted">{t(label)}</p>
          </Card>
        ))}
      </div>

      <SectionTitle title={t("admin.last14Days")} />
      <Card>
        <ul className="flex flex-col gap-1.5">
          {overview.daily.map((point) => (
            <li key={point.date} className="flex items-center gap-2 text-xs">
              <span className="w-16 shrink-0 text-ink-muted">{point.date.slice(5)}</span>
              <span className="h-2 flex-1 overflow-hidden rounded-full bg-lavender-soft">
                <span
                  className="block h-full rounded-full bg-primary"
                  style={{ width: `${Math.round((point.bookings / maxBookings) * 100)}%` }}
                />
              </span>
              <span className="w-8 shrink-0 text-end font-bold text-ink">{formatNumber(point.bookings)}</span>
              <span className="w-24 shrink-0 text-end text-ink-muted">{formatCurrency(point.revenue)}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[11px] text-ink-muted">
          {t("admin.bookingsPerDay")} · {t("admin.revenuePerDay")}
        </p>
      </Card>
    </>
  );
}
