"use client";

import { Check } from "lucide-react";
import { Page } from "@/components/layout/page";
import { BookingSummary } from "@/components/booking/booking-summary";
import { LinkButton } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useI18n } from "@/lib/i18n/provider";
import type { Doctor } from "@/types/doctor";
import type { Clinic } from "@/types/clinic";
import type { Availability } from "@/types/availability";
import type { Payment } from "@/types/payment";

/** The "Appointment Confirmed" screen, after paying online or choosing to pay at the clinic. */
export function BookingConfirmed({
  doctor,
  clinic,
  slot,
  payment,
}: {
  doctor: Doctor;
  clinic: Clinic;
  slot: Availability;
  payment: Payment;
}) {
  const { t, formatCurrency } = useI18n();
  const paid = payment.status === "paid";

  return (
    <Page width="narrow">
      <p className="mb-4 text-center text-sm font-bold text-ink">{t("confirmation.title")}</p>
      <div className="mx-auto mb-3 mt-8 grid h-[72px] w-[72px] place-items-center rounded-full bg-primary-soft text-primary-dark">
        <Check className="h-9 w-9" strokeWidth={2} />
      </div>
      <div className="mb-5 text-center">
        <h1 className="text-[25px] font-bold text-ink">{t("confirmation.heading")}</h1>
        <p className="mt-1 text-sm text-ink-muted">{t("confirmation.subtitle")}</p>
      </div>
      <BookingSummary doctor={doctor} clinic={clinic} slot={slot} />
      <Card className="mt-2.5 text-sm">
        <div className="flex items-center justify-between gap-3">
          <span className="text-ink-muted">{paid ? t("confirmation.paid") : t("confirmation.payAtClinic")}</span>
          <span className="font-bold text-ink">
            {payment.amount != null ? formatCurrency(payment.amount) : t("payment.feeValue")}
          </span>
        </div>
      </Card>
      <LinkButton href="/appointments" block className="mt-[15px]">
        {t("confirmation.view")}
      </LinkButton>
      <LinkButton href="/" variant="secondary" block className="mt-[9px]">
        {t("confirmation.home")}
      </LinkButton>
    </Page>
  );
}
