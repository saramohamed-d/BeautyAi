"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CreditCard, Smartphone, CheckCircle2, Calendar, Clock, MapPin, Stethoscope } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useBookingContext } from "@/lib/booking-context";
import { usePatientContext } from "@/lib/patient-context";
import { useCreateAppointment } from "@/hooks/use-create-appointment";
import { formatDateArabic, formatTime } from "@/lib/format";
import { ApiError } from "@/lib/api-client";

type PaymentMethod = "card" | "instapay";

/**
 * Payment — UI ONLY. No payment provider is integrated, no card details
 * are collected or stored anywhere (not even in memory) — the person
 * only picks a method. "Confirm" creates the real Appointment via
 * Sprint 2's POST /appointments; nothing here simulates a charge.
 */
export default function PaymentPage() {
  const router = useRouter();
  const { draft, resetDraft } = useBookingContext();
  const { patient } = usePatientContext();
  const [method, setMethod] = useState<PaymentMethod>("card");
  const [confirmedId, setConfirmedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { mutate, isPending } = useCreateAppointment();

  if (!draft.doctor || !draft.clinic || !draft.slot || !patient) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16 text-center md:px-6">
        <p className="text-lg font-semibold text-ink">لا يوجد حجز قيد الإتمام</p>
        <p className="mt-2 text-ink-muted">ابدئي عملية الحجز أولاً لاختيار طبيبك وموعدك.</p>
        <Link href="/booking" className="mt-6 inline-block">
          <Button>ابدئي الحجز</Button>
        </Link>
      </div>
    );
  }

  if (confirmedId) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16 text-center md:px-6">
        <CheckCircle2 className="mx-auto h-14 w-14 text-sage" strokeWidth={1.5} />
        <h1 className="mt-4 text-2xl font-bold text-ink">تم تأكيد حجزك</h1>
        <p className="mt-2 text-ink-muted">
          موعدك مع {draft.doctor.full_name} في {draft.clinic.name} تم تأكيده بنجاح.
        </p>
        <div className="mt-6 flex flex-col gap-2 rounded-2xl border border-border bg-surface p-5 text-right text-sm">
          <span className="flex items-center gap-2 text-ink"><Calendar className="h-4 w-4 text-primary" /> {formatDateArabic(new Date(draft.slot.start_time))}</span>
          <span className="flex items-center gap-2 text-ink"><Clock className="h-4 w-4 text-primary" /> {formatTime(new Date(draft.slot.start_time))}</span>
        </div>
        <Link href="/appointments" className="mt-6 inline-block">
          <Button size="lg">عرض مواعيدي</Button>
        </Link>
      </div>
    );
  }

  function handleConfirm() {
    if (!draft.doctor || !draft.clinic || !draft.slot || !patient) return;
    setError(null);
    mutate(
      {
        patient_id: patient.id,
        doctor_id: draft.doctor.id,
        clinic_id: draft.clinic.id,
        availability_id: draft.slot.id,
        scheduled_start: draft.slot.start_time,
        scheduled_end: draft.slot.end_time,
        notes: draft.notes || undefined,
        idempotency_key: crypto.randomUUID(),
      },
      {
        onSuccess: (appointment) => {
          setConfirmedId(appointment.id);
          resetDraft();
        },
        onError: (err) => {
          setError(err instanceof ApiError ? err.message : "تعذر تأكيد الحجز. حاولي مرة أخرى.");
        },
      }
    );
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-12 md:px-6">
      <h1 className="text-2xl font-bold text-ink md:text-3xl">الدفع</h1>
      <p className="mt-2 text-ink-muted">اختاري طريقة الدفع لتأكيد حجزك.</p>

      <div className="mt-6 rounded-2xl border border-border bg-surface p-5">
        <p className="mb-3 font-semibold text-ink">ملخص الحجز</p>
        <dl className="flex flex-col gap-2 text-sm text-ink-muted">
          <div className="flex items-center gap-2"><Stethoscope className="h-4 w-4" /> {draft.doctor.full_name}</div>
          <div className="flex items-center gap-2"><MapPin className="h-4 w-4" /> {draft.clinic.name}</div>
          <div className="flex items-center gap-2"><Calendar className="h-4 w-4" /> {formatDateArabic(new Date(draft.slot.start_time))}</div>
          <div className="flex items-center gap-2"><Clock className="h-4 w-4" /> {formatTime(new Date(draft.slot.start_time))}</div>
        </dl>
      </div>

      <div className="mt-6 flex flex-col gap-3">
        <button
          type="button"
          onClick={() => setMethod("card")}
          className={cn(
            "flex items-center gap-3 rounded-2xl border p-4 text-right transition-colors",
            method === "card" ? "border-primary bg-primary-soft" : "border-border bg-surface"
          )}
          aria-pressed={method === "card"}
        >
          <CreditCard className="h-5 w-5 text-primary-dark" />
          <div>
            <p className="font-semibold text-ink">فيزا / بطاقة ائتمان</p>
            <p className="text-sm text-ink-muted">الدفع الفعلي غير مفعّل حالياً — هذه واجهة تجريبية.</p>
          </div>
        </button>

        <button
          type="button"
          onClick={() => setMethod("instapay")}
          className={cn(
            "flex items-center gap-3 rounded-2xl border p-4 text-right transition-colors",
            method === "instapay" ? "border-primary bg-primary-soft" : "border-border bg-surface"
          )}
          aria-pressed={method === "instapay"}
        >
          <Smartphone className="h-5 w-5 text-primary-dark" />
          <div>
            <p className="font-semibold text-ink">InstaPay</p>
            <p className="text-sm text-ink-muted">الدفع الفعلي غير مفعّل حالياً — هذه واجهة تجريبية.</p>
          </div>
        </button>
      </div>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      <Button size="lg" className="mt-6 w-full" onClick={handleConfirm} disabled={isPending}>
        {isPending ? "جاري تأكيد الحجز..." : "تأكيد الحجز"}
      </Button>
    </div>
  );
}
