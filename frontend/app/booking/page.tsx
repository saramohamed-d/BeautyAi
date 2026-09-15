"use client";

import { Suspense, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Stepper } from "@/components/booking/stepper";
import { DoctorSelectStep } from "@/components/booking/doctor-select-step";
import { ClinicSelectStep } from "@/components/booking/clinic-select-step";
import { BookingCalendar } from "@/components/booking/calendar";
import { TimeSlotGrid } from "@/components/booking/time-slot-grid";
import { ReviewStep, type PatientDetailsValues } from "@/components/booking/review-step";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useBookingContext } from "@/lib/booking-context";
import { usePatientContext } from "@/lib/patient-context";
import { useDoctor } from "@/hooks/use-doctor";
import { useAvailability } from "@/hooks/use-availability";
import { findOrCreatePatient } from "@/services/patient-service";
import { isSameDay, startOfDay } from "@/lib/format";
import { ApiError } from "@/lib/api-client";
import type { Availability } from "@/types/availability";

const STEP_LABELS = ["الطبيب", "العيادة", "الموعد", "بياناتك"];

/**
 * Booking wizard. Maps to the brief's 7-step flow as follows: steps 1-2
 * (doctor, clinic) are their own UI steps; steps 3-4 (date, time) are
 * combined into one UI step since picking a date naturally surfaces
 * that date's times right below it; step 5 (review) also collects the
 * patient-identifying details this sprint needs in place of real auth.
 * Steps 6-7 (payment, confirmation) live on /payment — see BookingContext.
 */
function BookingPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const preselectedDoctorId = searchParams.get("doctorId") ?? undefined;

  const { draft, setDraft } = useBookingContext();
  const { setPatient } = usePatientContext();
  const { data: preselectedDoctor } = useDoctor(preselectedDoctorId);

  const [step, setStep] = useState(0);
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Auto-advance past step 1 if a doctor was pre-selected via ?doctorId=
  const effectiveDoctor = draft.doctor ?? preselectedDoctor ?? null;

  const { data: slotsData, isLoading: slotsLoading } = useAvailability(
    { doctor_id: effectiveDoctor?.id, clinic_id: draft.clinic?.id, is_booked: false, page_size: 100 },
    Boolean(effectiveDoctor && draft.clinic)
  );

  const datesWithSlots = useMemo(
    () => (slotsData ? slotsData.items.map((s) => startOfDay(new Date(s.start_time))) : []),
    [slotsData]
  );

  const slotsForSelectedDate: Availability[] = useMemo(() => {
    if (!slotsData || !selectedDate) return [];
    return slotsData.items
      .filter((s) => isSameDay(new Date(s.start_time), selectedDate))
      .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());
  }, [slotsData, selectedDate]);

  async function handleReviewSubmit(values: PatientDetailsValues) {
    if (!draft.doctor || !draft.clinic || !draft.slot) return;
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const patient = await findOrCreatePatient({
        full_name: values.full_name,
        phone: values.phone,
        email: values.email || undefined,
      });
      setPatient(patient);
      router.push("/payment");
    } catch (err) {
      setSubmitError(
        err instanceof ApiError ? err.message : "حدث خطأ أثناء حفظ بياناتك. حاولي مرة أخرى."
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 md:px-6">
      <h1 className="text-2xl font-bold text-ink md:text-3xl">احجزي موعدك</h1>
      <p className="mt-2 text-ink-muted">اختاري طبيبك والعيادة والموعد المناسب لك.</p>

      <div className="mt-6">
        <Stepper steps={STEP_LABELS} currentStep={step + 1} />
      </div>

      <div className="mt-8 rounded-3xl border border-border bg-surface p-6 md:p-8">
        {step === 0 && (
          <DoctorSelectStep
            selectedDoctor={effectiveDoctor}
            onSelect={(doctor) => {
              setDraft((prev) => ({ ...prev, doctor, clinic: null, slot: null }));
              setSelectedDate(null);
              setStep(1);
            }}
          />
        )}

        {step === 1 && effectiveDoctor && (
          <ClinicSelectStep
            doctorId={effectiveDoctor.id}
            selectedClinic={draft.clinic}
            onSelect={(clinic) => {
              setDraft((prev) => ({ ...prev, clinic, slot: null }));
              setSelectedDate(null);
              setStep(2);
            }}
          />
        )}

        {step === 2 && draft.clinic && (
          <div className="flex flex-col gap-6">
            <div>
              <p className="mb-3 font-semibold text-ink">اختاري التاريخ</p>
              {slotsLoading ? (
                <Skeleton className="h-20" />
              ) : (
                <BookingCalendar selectedDate={selectedDate} onSelect={setSelectedDate} datesWithSlots={datesWithSlots} />
              )}
            </div>
            {selectedDate && (
              <div>
                <p className="mb-3 font-semibold text-ink">اختاري الوقت</p>
                <TimeSlotGrid
                  slots={slotsForSelectedDate}
                  selectedSlot={draft.slot}
                  onSelect={(slot) => {
                    setDraft((prev) => ({ ...prev, slot }));
                    setStep(3);
                  }}
                />
              </div>
            )}
          </div>
        )}

        {step === 3 && draft.doctor && draft.clinic && draft.slot && (
          <>
            <ReviewStep draft={draft} isSubmitting={isSubmitting} onSubmit={handleReviewSubmit} />
            {submitError && <p className="mt-3 text-sm text-red-600">{submitError}</p>}
          </>
        )}
      </div>

      {step > 0 && (
        <Button variant="ghost" size="sm" className="mt-4" onClick={() => setStep((s) => Math.max(0, s - 1))}>
          رجوع للخطوة السابقة
        </Button>
      )}
    </div>
  );
}

export default function BookingPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-3xl px-4 py-12 md:px-6"><Skeleton className="h-96" /></div>}>
      <BookingPageContent />
    </Suspense>
  );
}
