"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { DoctorSelectStep } from "@/components/booking/doctor-select-step";
import { ClinicSelectStep } from "@/components/booking/clinic-select-step";
import { BookingCalendar } from "@/components/booking/calendar";
import { TimeSlotGrid } from "@/components/booking/time-slot-grid";
import { ReviewStep } from "@/components/booking/review-step";
import { SignInRequired } from "@/components/auth/sign-in-required";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useBookingContext } from "@/lib/booking-context";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/types";
import { useDoctor } from "@/hooks/use-doctor";
import { useStartCheckout } from "@/hooks/use-start-checkout";
import { useAvailability } from "@/hooks/use-availability";
import { isSameDay, startOfDay } from "@/lib/format";
import type { Availability } from "@/types/availability";

const STEPS: { heading: MessageKey; progress: number }[] = [
  { heading: "booking.headings.doctor", progress: 25 },
  { heading: "booking.headings.clinic", progress: 50 },
  { heading: "booking.headings.date", progress: 72 },
  { heading: "booking.headings.details", progress: 85 },
];
const TIME_STEP = 2;
const DETAILS_STEP = 3;

/**
 * Booking wizard: doctor → clinic → date & time → review/details, then
 * /payment (payment + confirmation). The draft lives in BookingContext.
 *
 * Entry points:
 *   ?doctorId=…      from a doctor profile — starts at the clinic step
 *   ?step=details    from the AI assistant or after logging in mid-booking;
 *                    the draft is already filled
 *   ?step=time       from payment when the chosen time was taken; doctor
 *                    and clinic are kept
 *
 * "Continue to payment" places a server-side hold on the slot (see
 * hooks/use-start-checkout.ts) so nobody else can book it mid-payment.
 *
 * Browsing and choosing a slot is open to everyone; the review step asks
 * logged-out visitors to log in, then brings them back here.
 */
function BookingPageContent() {
  const { t } = useI18n();
  const searchParams = useSearchParams();
  const preselectedDoctorId = searchParams.get("doctorId") ?? undefined;

  const { draft, setDraft } = useBookingContext();
  const { status, patient } = useAuth();
  const { data: preselectedDoctor } = useDoctor(preselectedDoctorId);

  const draftComplete = Boolean(draft.doctor && draft.clinic && draft.slot);
  const [step, setStep] = useState(() => {
    const requested = searchParams.get("step");
    if (requested === "details" && draftComplete) return DETAILS_STEP;
    if (requested === "time" && draft.doctor && draft.clinic) return TIME_STEP;
    return 0;
  });
  const { startCheckout, isHolding, error: checkoutError } = useStartCheckout();
  const [slotTaken, setSlotTaken] = useState(searchParams.get("step") === "time");

  // Someone else got the slot while this patient was reviewing: back to the times.
  useEffect(() => {
    if (checkoutError === "taken") {
      setSlotTaken(true);
      setStep(TIME_STEP);
    }
  }, [checkoutError]);
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);

  // Arriving from a doctor profile: put that doctor in the draft and skip ahead.
  useEffect(() => {
    if (!preselectedDoctor) return;
    setDraft((prev) =>
      prev.doctor?.id === preselectedDoctor.id ? prev : { ...prev, doctor: preselectedDoctor, clinic: null, slot: null }
    );
    setStep((s) => (s === 0 ? 1 : s));
  }, [preselectedDoctor, setDraft]);

  const { data: slotsData, isLoading: slotsLoading } = useAvailability(
    { doctor_id: draft.doctor?.id, clinic_id: draft.clinic?.id, available: true, page_size: 100 },
    Boolean(draft.doctor && draft.clinic)
  );

  const datesWithSlots = useMemo(
    () => (slotsData ? slotsData.items.map((s) => startOfDay(new Date(s.start_time))) : []),
    [slotsData]
  );

  const slotsForSelectedDate: Availability[] = useMemo(() => {
    if (!slotsData || !selectedDate) return [];
    return slotsData.items
      .filter((s) => isSameDay(new Date(s.start_time), selectedDate))
      .sort((a, b) => +new Date(a.start_time) - +new Date(b.start_time));
  }, [slotsData, selectedDate]);

  const current = STEPS[step] ?? STEPS[0]!;

  return (
    <Page width="narrow">
      <PageHeader title={t("booking.title")} onBack={step > 0 ? () => setStep((s) => s - 1) : undefined} />
      <Progress value={current.progress} />
      <h2 className="mb-4 mt-2 text-[25px] font-bold leading-tight text-ink">{t(current.heading)}</h2>

      {step === 0 && (
        <DoctorSelectStep
          selectedDoctor={draft.doctor}
          onSelect={(doctor) => {
            setDraft((prev) => ({ ...prev, doctor, clinic: null, slot: null }));
            setSelectedDate(null);
            setStep(1);
          }}
        />
      )}

      {step === 1 && draft.doctor && (
        <ClinicSelectStep
          doctorId={draft.doctor.id}
          selectedClinic={draft.clinic}
          onSelect={(clinic) => {
            setDraft((prev) => ({ ...prev, clinic, slot: null }));
            setSelectedDate(null);
            setStep(2);
          }}
        />
      )}

      {step === TIME_STEP && draft.clinic && (
        <div className="flex flex-col gap-2.5">
          {slotTaken && (
            <p role="alert" className="rounded-card bg-primary-soft p-3 text-sm text-primary-dark">
              {t("booking.taken")}
            </p>
          )}
          <Card>
            <p className="mb-3 text-sm font-bold text-ink">{t("booking.date")}</p>
            {slotsLoading ? (
              <Skeleton className="h-16" />
            ) : (
              <BookingCalendar selectedDate={selectedDate} onSelect={setSelectedDate} datesWithSlots={datesWithSlots} />
            )}
          </Card>
          {selectedDate && (
            <div>
              <p className="mb-2 mt-2 text-sm font-bold text-ink">{t("booking.times")}</p>
              <TimeSlotGrid
                slots={slotsForSelectedDate}
                selectedSlot={draft.slot}
                onSelect={(slot) => {
                  setSlotTaken(false);
                  setDraft((prev) => ({ ...prev, slot, heldUntil: null }));
                }}
              />
            </div>
          )}
          <Button block className="mt-[15px]" disabled={!draft.slot} onClick={() => setStep(DETAILS_STEP)}>
            {t("common.continue")}
          </Button>
        </div>
      )}

      {step === DETAILS_STEP &&
        draftComplete &&
        (status === "loading" ? (
          <Skeleton className="h-64" />
        ) : patient ? (
          <ReviewStep
            draft={draft}
            patient={patient}
            isHolding={isHolding}
            failed={checkoutError === "generic"}
            onContinue={() => draft.slot && startCheckout(draft.slot)}
          />
        ) : (
          <SignInRequired next="/booking?step=details" />
        ))}
    </Page>
  );
}

export default function BookingPage() {
  return (
    <Suspense fallback={<Page width="narrow"><Skeleton className="h-96" /></Page>}>
      <BookingPageContent />
    </Suspense>
  );
}
