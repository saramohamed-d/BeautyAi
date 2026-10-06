"use client";

import { CalendarDays, MapPin } from "lucide-react";
import { DoctorAvatar } from "@/components/doctors/doctor-avatar";
import { Card } from "@/components/ui/card";
import { useI18n } from "@/lib/i18n/provider";
import type { Doctor } from "@/types/doctor";
import type { Clinic } from "@/types/clinic";
import type { Availability } from "@/types/availability";

/** Doctor / clinic / date-time card shown on review, payment and confirmation. */
export function BookingSummary({ doctor, clinic, slot }: { doctor: Doctor; clinic: Clinic; slot: Availability }) {
  const { label, formatDate, formatTime } = useI18n();
  const start = new Date(slot.start_time);

  return (
    <Card className="flex items-start gap-[11px]">
      <DoctorAvatar avatar={doctor.avatar} />
      <div className="min-w-0 flex-1 text-xs text-ink-muted">
        <p className="text-sm font-bold text-ink">{doctor.full_name}</p>
        <p className="mt-0.5">{label("specialties", doctor.specialty)}</p>
        <p className="mt-1.5 flex items-center gap-1.5">
          <MapPin className="h-3.5 w-3.5 shrink-0" /> {clinic.name} · {clinic.city}
        </p>
        <p className="mt-1 flex items-center gap-1.5">
          <CalendarDays className="h-3.5 w-3.5 shrink-0" /> {formatDate(start, "long")} · {formatTime(start)}
        </p>
      </div>
    </Card>
  );
}
