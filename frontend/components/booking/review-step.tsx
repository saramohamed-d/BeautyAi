"use client";

import { UserRound } from "lucide-react";
import { BookingSummary } from "@/components/booking/booking-summary";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n/provider";
import type { BookingDraft } from "@/lib/booking-context";
import type { Patient } from "@/types/patient";

/** Final check before payment: what is being booked, and for whom (the logged-in patient). */
export function ReviewStep({
  draft,
  patient,
  onContinue,
  isHolding,
  failed,
}: {
  draft: BookingDraft;
  patient: Patient;
  onContinue: () => void;
  isHolding: boolean;
  failed: boolean;
}) {
  const { t } = useI18n();

  return (
    <div className="flex flex-col gap-2.5">
      {draft.doctor && draft.clinic && draft.slot && (
        <BookingSummary doctor={draft.doctor} clinic={draft.clinic} slot={draft.slot} />
      )}
      <Card className="flex items-center gap-[11px]">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-lavender-soft text-ink">
          <UserRound className="h-5 w-5" strokeWidth={1.75} />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-ink-muted">{t("booking.bookingFor")}</p>
          <p className="truncate text-sm font-bold text-ink">{patient.full_name}</p>
          <p className="text-xs text-ink-muted" dir="ltr">
            {patient.phone}
          </p>
        </div>
      </Card>
      {failed && (
        <p role="alert" className="text-sm text-red-700">
          {t("errors.generic")}
        </p>
      )}
      <Button block className="mt-[5px]" onClick={onContinue} disabled={isHolding}>
        {isHolding ? t("booking.holding") : t("booking.continueToPayment")}
      </Button>
    </div>
  );
}
