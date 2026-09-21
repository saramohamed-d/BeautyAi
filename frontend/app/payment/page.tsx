"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Banknote, Clock, CreditCard, Lock, Smartphone, type LucideIcon } from "lucide-react";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { BookingSummary } from "@/components/booking/booking-summary";
import { BookingConfirmed } from "@/components/booking/booking-confirmed";
import { Button, LinkButton } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { SelectableCard } from "@/components/ui/selectable-card";
import { useBookingContext } from "@/lib/booking-context";
import { useAuth } from "@/lib/auth-context";
import { SignInRequired } from "@/components/auth/sign-in-required";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/types";
import { useCountdown } from "@/hooks/use-countdown";
import { releaseHold } from "@/services/availability-service";
import { fetchPaymentQuote, startCheckout } from "@/services/payment-service";
import { Notice } from "@/components/ui/notice";
import { ApiError } from "@/lib/api-client";
import type { Doctor } from "@/types/doctor";
import type { Clinic } from "@/types/clinic";
import type { Availability } from "@/types/availability";
import type { Payment, PaymentMethod } from "@/types/payment";

const METHODS: Record<PaymentMethod, { icon: LucideIcon; title: MessageKey; sub: MessageKey }> = {
  card: { icon: CreditCard, title: "payment.card", sub: "payment.cardSub" },
  wallet: { icon: Smartphone, title: "payment.wallet", sub: "payment.walletSub" },
  pay_at_clinic: { icon: Banknote, title: "payment.clinic", sub: "payment.clinicSub" },
};

interface ConfirmedBooking {
  doctor: Doctor;
  clinic: Clinic;
  slot: Availability;
  payment: Payment;
}

/**
 * Payment (Sprint 11; docs/payments.md).
 *
 * The methods and fee come from GET /payments/quote. Card and mobile
 * wallet send the patient to the payment provider's own secure page (we
 * never see card details); the appointment is created only when the
 * provider confirms the payment to our server, and /payment/return shows
 * the result. "Pay at clinic" books immediately.
 *
 * One idempotency key per visit to this page: a retried click can never
 * start two payments.
 */
export default function PaymentPage() {
  const { t, formatCurrency } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { draft, setDraft, resetDraft } = useBookingContext();
  const { status, patient } = useAuth();
  const [method, setMethod] = useState<PaymentMethod | null>(null);
  const [confirmed, setConfirmed] = useState<ConfirmedBooking | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [taken, setTaken] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [idempotencyKey] = useState(() => crypto.randomUUID());
  const secondsLeft = useCountdown(draft.heldUntil);

  const { doctor, clinic, slot } = draft;
  const quote = useQuery({
    queryKey: ["payment-quote", slot?.id],
    queryFn: () => fetchPaymentQuote(slot!.id),
    enabled: Boolean(slot && patient),
  });

  // Default to the first method offered (card when online payment is available).
  useEffect(() => {
    if (quote.data && (method === null || !quote.data.methods.includes(method))) setMethod(quote.data.methods[0] ?? null);
  }, [quote.data, method]);

  if (confirmed) return <BookingConfirmed {...confirmed} />;

  if (doctor && clinic && slot && !patient) {
    return (
      <Page width="narrow">
        <PageHeader title={t("payment.title")} backHref="/booking?step=details" />
        {status === "loading" ? <Skeleton className="h-64" /> : <SignInRequired next="/payment" />}
      </Page>
    );
  }
  if (!doctor || !clinic || !slot || !patient) {
    return (
      <Page width="narrow">
        <PageHeader title={t("payment.title")} backHref="/booking" />
        <Card className="mt-8 text-center">
          <p className="font-bold text-ink">{t("payment.noDraftTitle")}</p>
          <p className="mt-1 text-sm text-ink-muted">{t("payment.noDraftBody")}</p>
          <LinkButton href="/booking" block className="mt-4">
            {t("payment.noDraftCta")}
          </LinkButton>
        </Card>
      </Page>
    );
  }

  const online = method === "card" || method === "wallet";

  async function handleConfirm() {
    if (!doctor || !clinic || !slot || !method) return;
    setError(null);
    setSubmitting(true);
    try {
      const result = await startCheckout({ availability_id: slot.id, method, idempotency_key: idempotencyKey });
      if (result.checkout_url) {
        // Off to the provider's page; the provider brings the patient back to /payment/return.
        window.location.assign(result.checkout_url);
        return;
      }
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
      queryClient.invalidateQueries({ queryKey: ["availability"] });
      setConfirmed({ doctor, clinic, slot, payment: result.payment });
      resetDraft();
    } catch (err) {
      if (err instanceof ApiError && err.code === "slot_unavailable") setTaken(true);
      else if (err instanceof ApiError && err.code === "online_payment_unavailable") setError(t("payment.onlineUnavailable"));
      else if (err instanceof ApiError && err.code === "payment_provider_error") setError(t("payment.providerDown"));
      else setError(t("errors.generic"));
    }
    setSubmitting(false);
  }

  return (
    <Page width="narrow">
      <PageHeader
        title={t("payment.title")}
        onBack={() => {
          // Going back frees the time for others right away (it would expire anyway).
          releaseHold(slot.id).catch(() => undefined);
          setDraft((prev) => ({ ...prev, heldUntil: null }));
          router.push("/booking?step=details");
        }}
      />
      <Progress value={90} />
      <h2 className="mt-2 text-[25px] font-bold leading-tight text-ink">{t("payment.heading")}</h2>
      <p className="mt-1 text-sm text-ink-muted">{t("payment.subtitle")}</p>

      {quote.isLoading ? (
        <Skeleton className="mt-4 h-40" />
      ) : quote.isError ? (
        <p role="alert" className="mt-4 text-sm text-red-700">{t("errors.generic")}</p>
      ) : (
        <div className="mt-4 flex flex-col gap-2" role="radiogroup" aria-label={t("payment.heading")}>
          {quote.data?.methods.map((id) => {
            const { icon: Icon, title, sub } = METHODS[id];
            return (
              <SelectableCard key={id} selected={method === id} onClick={() => setMethod(id)} role="radio" aria-checked={method === id}>
                <Icon className="h-5 w-5 shrink-0 text-primary-dark" strokeWidth={1.75} />
                <div>
                  <p className="text-sm font-bold text-ink">{t(title)}</p>
                  <p className="text-xs text-ink-muted">{t(sub)}</p>
                </div>
              </SelectableCard>
            );
          })}
          {quote.data?.amount == null && <p className="text-xs text-ink-muted">{t("payment.onlyAtClinic")}</p>}
        </div>
      )}

      <div className="mt-2.5">
        <BookingSummary doctor={doctor} clinic={clinic} slot={slot} />
      </div>

      <Card className="mt-2.5 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-ink-muted">{t("payment.fee")}</span>
          <span className="font-bold text-ink">
            {quote.data?.amount != null ? formatCurrency(quote.data.amount) : t("payment.feeValue")}
          </span>
        </div>
      </Card>

      {secondsLeft !== null && !taken && (
        <p className="mt-3 flex items-center gap-1.5 text-sm text-ink-muted" aria-live="polite">
          <Clock className="h-4 w-4 text-primary-dark" aria-hidden="true" />
          {secondsLeft > 0
            ? t("payment.heldFor", {
                time: `${Math.floor(secondsLeft / 60)}:${String(secondsLeft % 60).padStart(2, "0")}`,
              })
            : t("payment.holdExpired")}
        </p>
      )}

      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}

      {taken ? (
        <Notice className="mt-[15px]" role="alert">
          <p>{t("booking.taken")}</p>
          <Button
            block
            className="mt-3"
            onClick={() => {
              setDraft((prev) => ({ ...prev, slot: null, heldUntil: null }));
              router.push("/booking?step=time");
            }}
          >
            {t("booking.chooseAnother")}
          </Button>
        </Notice>
      ) : (
        <Button block className="mt-[15px]" onClick={handleConfirm} disabled={submitting || !method}>
          {submitting ? t("payment.confirming") : online ? t("payment.payOnline") : t("payment.confirmAtClinic")}
        </Button>
      )}
      {online && (
        <p className="mt-2 flex items-center justify-center gap-1.5 text-center text-xs text-ink-muted">
          <Lock className="h-3.5 w-3.5" aria-hidden="true" />
          {t("payment.secureNote")}
        </p>
      )}
    </Page>
  );
}
