"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Calendar, Clock, MapPin, Stethoscope } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { formatDateArabic, formatTime } from "@/lib/format";
import type { BookingDraft } from "@/lib/booking-context";

const patientDetailsSchema = z.object({
  full_name: z.string().min(2, "الاسم لازم يكون حرفين على الأقل"),
  phone: z
    .string()
    .regex(/^\+?[0-9]{8,15}$/, "رقم الهاتف غير صحيح (8-15 رقم)"),
  email: z.union([z.string().email("بريد إلكتروني غير صحيح"), z.literal("")]).optional(),
});

export type PatientDetailsValues = z.infer<typeof patientDetailsSchema>;

/**
 * Combines the appointment summary (step 5 in the brief: "review
 * appointment details") with the minimal patient-details form needed to
 * identify a real Patient row — since Sprint 3 has no backend auth,
 * this form is effectively step 5's "who is this for" question,
 * answered against the real Patients API (see services/patient-service.ts),
 * not an invented login.
 */
export function ReviewStep({
  draft,
  defaultValues,
  isSubmitting,
  onSubmit,
}: {
  draft: BookingDraft;
  defaultValues?: Partial<PatientDetailsValues>;
  isSubmitting: boolean;
  onSubmit: (values: PatientDetailsValues) => void;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<PatientDetailsValues>({
    resolver: zodResolver(patientDetailsSchema),
    defaultValues: { full_name: "", phone: "", email: "", ...defaultValues },
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-2xl border border-border bg-surface p-5">
        <p className="mb-3 font-semibold text-ink">ملخص الحجز</p>
        <dl className="flex flex-col gap-2.5 text-sm">
          <div className="flex items-center gap-2 text-ink-muted">
            <Stethoscope className="h-4 w-4" />
            <dt className="sr-only">الطبيب</dt>
            <dd className="text-ink">{draft.doctor?.full_name}</dd>
          </div>
          <div className="flex items-center gap-2 text-ink-muted">
            <MapPin className="h-4 w-4" />
            <dt className="sr-only">العيادة</dt>
            <dd className="text-ink">{draft.clinic?.name}</dd>
          </div>
          {draft.slot && (
            <>
              <div className="flex items-center gap-2 text-ink-muted">
                <Calendar className="h-4 w-4" />
                <dt className="sr-only">التاريخ</dt>
                <dd className="text-ink">{formatDateArabic(new Date(draft.slot.start_time))}</dd>
              </div>
              <div className="flex items-center gap-2 text-ink-muted">
                <Clock className="h-4 w-4" />
                <dt className="sr-only">الوقت</dt>
                <dd className="text-ink">{formatTime(new Date(draft.slot.start_time))}</dd>
              </div>
            </>
          )}
        </dl>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
        <p className="font-semibold text-ink">بياناتك</p>
        <Input label="الاسم بالكامل" placeholder="اسمك بالكامل" error={errors.full_name?.message} {...register("full_name")} />
        <Input label="رقم الهاتف" placeholder="01xxxxxxxxx" dir="ltr" error={errors.phone?.message} {...register("phone")} />
        <Input label="البريد الإلكتروني (اختياري)" placeholder="example@mail.com" dir="ltr" error={errors.email?.message} {...register("email")} />

        <Button type="submit" size="lg" disabled={isSubmitting} className="mt-2">
          {isSubmitting ? "جاري المتابعة..." : "المتابعة للدفع"}
        </Button>
      </form>
    </div>
  );
}
