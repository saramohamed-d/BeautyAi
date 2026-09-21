"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Receipt } from "lucide-react";
import { AdminShell } from "@/components/admin/admin-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useI18n } from "@/lib/i18n/provider";
import { ApiError } from "@/lib/api-client";
import { LIVE } from "@/lib/query-options";
import { fetchPayments, refundPayment } from "@/services/admin-service";
import type { Payment, PaymentStatus } from "@/types/payment";

const FILTERS: (PaymentStatus | "all")[] = ["all", "needs_refund", "paid", "pending", "failed", "refunded"];
const TONES: Partial<Record<PaymentStatus, "primary" | "sage" | "neutral">> = {
  paid: "sage",
  refunded: "neutral",
  needs_refund: "primary",
  pending: "primary",
};
// Money has been taken, so a refund is still possible (backend REFUNDABLE).
const REFUNDABLE: PaymentStatus[] = ["paid", "needs_refund", "refund_pending"];

/** Every payment, starting with the ones a human has to fix (Sprint 14). */
export default function AdminPaymentsPage() {
  return <AdminShell>{() => <Payments />}</AdminShell>;
}

function Payments() {
  const { t, label } = useI18n();
  const [filter, setFilter] = useState<PaymentStatus | "all">("needs_refund");
  const payments = useQuery({
    queryKey: ["admin-payments", filter],
    queryFn: () => fetchPayments({ page_size: 100, ...(filter === "all" ? {} : { status: filter }) }),
    ...LIVE,
  });

  const items = payments.data?.items ?? [];

  return (
    <>
      <h2 className="text-lg font-bold text-ink">{t("admin.payments.title")}</h2>
      <p className="mt-1 text-sm text-ink-muted">{t("admin.payments.subtitle")}</p>

      <div className="-mx-[18px] mt-3 flex gap-1.5 overflow-x-auto px-[18px] pb-1" role="tablist">
        {FILTERS.map((option) => (
          <button
            key={option}
            type="button"
            role="tab"
            aria-selected={filter === option}
            onClick={() => setFilter(option)}
            className={`whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-bold ${
              filter === option ? "border-primary bg-primary text-white" : "border-border bg-surface text-ink-muted"
            }`}
          >
            {option === "all"
              ? t("admin.payments.filterAll")
              : option === "needs_refund"
                ? t("admin.payments.needsRefund")
                : label("paymentStatus", option)}
          </button>
        ))}
      </div>

      {payments.isLoading ? (
        <Skeleton className="mt-3 h-32" />
      ) : items.length === 0 ? (
        <div className="mt-3">
          <EmptyState icon={Receipt} title={t("admin.payments.empty")} description={t("admin.payments.emptyBody")} />
        </div>
      ) : (
        <ul className="mt-3 flex flex-col gap-2">
          {items.map((payment) => (
            <li key={payment.id}>
              <PaymentRow payment={payment} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function PaymentRow({ payment }: { payment: Payment }) {
  const { t, formatDate, formatCurrency, label } = useI18n();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refund = useMutation({
    mutationFn: () => refundPayment(payment.id, reason.trim() || "Refunded by an administrator"),
    onSuccess: (updated) => {
      setError(updated.status === "needs_refund" ? t("admin.payments.refundFailed") : null);
      queryClient.invalidateQueries({ queryKey: ["admin-payments"] });
      queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
    },
    onError: (err) =>
      setError(
        err instanceof ApiError && err.code === "payment_not_refundable"
          ? t("admin.payments.notRefundable")
          : t("errors.generic")
      ),
  });

  return (
    <Card className="text-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-bold text-ink">{payment.amount ? formatCurrency(payment.amount) : "—"}</p>
          <p className="mt-0.5 text-xs text-ink-muted">
            {formatDate(new Date(payment.created_at), "long")} · {label("paymentMethod", payment.method)} ·{" "}
            {payment.provider}
          </p>
          <p className="mt-0.5 text-xs text-ink-muted">
            {payment.appointment_id ? t("admin.payments.appointment") : t("admin.payments.noAppointment")}
            {payment.failure_reason ? ` · ${payment.failure_reason}` : ""}
          </p>
        </div>
        <Badge tone={TONES[payment.status] ?? "neutral"}>{label("paymentStatus", payment.status)}</Badge>
      </div>

      {REFUNDABLE.includes(payment.status) && (
        <>
          <div className="mt-2 flex items-end gap-2">
            <Input
              label={t("admin.payments.refundReason")}
              className="flex-1"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
            <Button
              variant="secondary"
              className="h-11 w-auto px-3 text-xs"
              disabled={refund.isPending}
              onClick={() => refund.mutate()}
            >
              {refund.isPending ? t("admin.payments.refunding") : t("admin.payments.refund")}
            </Button>
          </div>
          {error && (
            <p role="alert" className="mt-2 text-sm text-red-700">
              {error}
            </p>
          )}
        </>
      )}
    </Card>
  );
}
