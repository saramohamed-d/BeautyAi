"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Loader2, RotateCcw } from "lucide-react";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { BookingConfirmed } from "@/components/booking/booking-confirmed";
import { Button, LinkButton } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { SignInRequired } from "@/components/auth/sign-in-required";
import { useAuth } from "@/lib/auth-context";
import { useBookingContext } from "@/lib/booking-context";
import { useI18n } from "@/lib/i18n/provider";
import { ApiError } from "@/lib/api-client";
import { useDoctor } from "@/hooks/use-doctor";
import { useClinic } from "@/hooks/use-clinic";
import { fetchSlot } from "@/services/availability-service";
import { fetchPayment, startCheckout } from "@/services/payment-service";
import type { PaymentMethod } from "@/types/payment";

// How long to keep checking for the provider's confirmation before saying it's delayed.
const WAIT_MS = 90_000;
const POLL_MS = 2_000;

/**
 * Where the payment provider sends the patient back. The browser coming
 * back proves nothing: this page only READS the payment, whose status is
 * set by the provider's signed server-to-server notification.
 */
function PaymentReturn() {
  const { t } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useSearchParams();
  const paymentId = params.get("payment_id") ?? "";
  const { status: authStatus, patient } = useAuth();
  const { resetDraft } = useBookingContext();
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [waited, setWaited] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setWaited(true), WAIT_MS);
    return () => clearTimeout(timer);
  }, []);

  const payment = useQuery({
    queryKey: ["payment", paymentId],
    queryFn: () => fetchPayment(paymentId),
    enabled: Boolean(paymentId && patient),
    refetchInterval: (query) => (query.state.data?.status === "pending" && !waited ? POLL_MS : false),
  });
  const data = payment.data;
  const booked = data?.status === "paid" || data?.status === "due_at_clinic";
  const doctor = useDoctor(booked ? data?.doctor_id : undefined);
  const clinic = useClinic(booked ? data?.clinic_id : undefined);
  const slot = useQuery({
    queryKey: ["availability", "slot", data?.availability_id],
    queryFn: () => fetchSlot(data!.availability_id!),
    enabled: Boolean(booked && data?.availability_id),
  });

  useEffect(() => {
    if (booked) {
      resetDraft();
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
    }
  }, [booked, resetDraft, queryClient]);

  if (authStatus === "loading" || (patient && payment.isLoading)) {
    return (
      <Page width="narrow">
        <Skeleton className="mt-8 h-64" />
      </Page>
    );
  }
  if (!patient) {
    return (
      <Page width="narrow">
        <PageHeader title={t("payment.title")} backHref="/" />
        <SignInRequired next={`/payment/return?payment_id=${paymentId}`} />
      </Page>
    );
  }
  if (!data) {
    return (
      <Page width="narrow">
        <PageHeader title={t("payment.title")} backHref="/" />
        <Card className="mt-8 text-center">
          <p className="font-bold text-ink">{t("paymentReturn.notFound")}</p>
          <LinkButton href="/appointments" block className="mt-4">
            {t("confirmation.view")}
          </LinkButton>
        </Card>
      </Page>
    );
  }

  if (booked) {
    if (doctor.data && clinic.data && slot.data) {
      return <BookingConfirmed doctor={doctor.data} clinic={clinic.data} slot={slot.data} payment={data} />;
    }
    return (
      <Page width="narrow">
        <Skeleton className="mt-8 h-64" />
      </Page>
    );
  }

  async function retry(method: PaymentMethod) {
    if (!data?.availability_id) return;
    setRetrying(true);
    setRetryError(null);
    try {
      const result = await startCheckout({
        availability_id: data.availability_id,
        method,
        idempotency_key: crypto.randomUUID(),
      });
      if (result.checkout_url) {
        window.location.assign(result.checkout_url);
        return;
      }
      router.replace(`/payment/return?payment_id=${result.payment.id}`);
    } catch (err) {
      setRetryError(
        err instanceof ApiError && err.code === "slot_unavailable" ? t("paymentReturn.slotGone") : t("errors.generic")
      );
    }
    setRetrying(false);
  }

  if (data.status === "pending" && !waited) {
    return (
      <Page width="narrow">
        <div className="mt-16 flex flex-col items-center text-center" aria-live="polite">
          <Loader2 className="h-10 w-10 animate-spin text-primary-dark" aria-hidden="true" />
          <h1 className="mt-4 text-xl font-bold text-ink">{t("paymentReturn.checking")}</h1>
          <p className="mt-1 text-sm text-ink-muted">{t("paymentReturn.checkingBody")}</p>
        </div>
      </Page>
    );
  }

  const refunded = ["refund_pending", "refunded", "needs_refund"].includes(data.status);
  const failed = data.status === "failed" || data.status === "expired";
  const title = refunded
    ? t("paymentReturn.refundTitle")
    : failed
      ? t("paymentReturn.failedTitle")
      : t("paymentReturn.delayedTitle");
  const body = refunded
    ? t("paymentReturn.refundBody")
    : failed
      ? t("paymentReturn.failedBody")
      : t("paymentReturn.delayedBody");

  return (
    <Page width="narrow">
      <PageHeader title={t("payment.title")} backHref="/" />
      <Card className="mt-6 text-center">
        <AlertCircle className="mx-auto h-10 w-10 text-primary-dark" aria-hidden="true" />
        <h1 className="mt-3 text-xl font-bold text-ink">{title}</h1>
        <p className="mt-1 text-sm text-ink-muted">{body}</p>
      </Card>

      {retryError && <p role="alert" className="mt-3 text-sm text-red-700">{retryError}</p>}

      {failed && data.availability_id && (
        <>
          <Button block className="mt-[15px]" disabled={retrying} onClick={() => retry(data.method)}>
            <RotateCcw className="h-4 w-4" aria-hidden="true" /> {t("paymentReturn.tryAgain")}
          </Button>
          <Button block variant="secondary" className="mt-[9px]" disabled={retrying} onClick={() => retry("pay_at_clinic")}>
            {t("paymentReturn.payAtClinic")}
          </Button>
        </>
      )}
      {refunded && (
        <LinkButton href="/booking" block className="mt-[15px]">
          {t("booking.chooseAnother")}
        </LinkButton>
      )}
      <LinkButton href="/appointments" variant="secondary" block className="mt-[9px]">
        {t("confirmation.view")}
      </LinkButton>
    </Page>
  );
}

export default function PaymentReturnPage() {
  return (
    <Suspense fallback={<Page width="narrow"><Skeleton className="mt-8 h-64" /></Page>}>
      <PaymentReturn />
    </Suspense>
  );
}
