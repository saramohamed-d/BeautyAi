"use client";

import Link from "next/link";
import { CalendarClock, ShieldCheck, Star } from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { useI18n } from "@/lib/i18n/provider";
import type { Doctor } from "@/types/doctor";
import type { Availability } from "@/types/availability";

/**
 * Doctor row card (the demo's `.card.doctor`); the whole card links to the
 * profile. Search results also pass the next bookable slot and starting price.
 */
export function DoctorCard({
  doctor,
  nextSlot,
  priceFrom,
}: {
  doctor: Doctor;
  nextSlot?: Availability | null;
  priceFrom?: number | null;
}) {
  const { t, label, formatNumber, formatDate, formatTime, formatCurrency } = useI18n();

  return (
    <Link
      href={`/doctors/${doctor.id}`}
      className="flex items-center gap-[11px] rounded-card border border-border bg-surface p-3 transition-colors hover:border-primary-line"
    >
      <Avatar name={doctor.full_name} />
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1.5 truncate text-sm font-bold text-ink">
          {doctor.full_name}
          {doctor.verification_status === "verified" && (
            <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-sage" aria-label={t("common.verified")} />
          )}
        </p>
        <p className="mt-0.5 truncate text-xs text-ink-muted">
          {label("specialties", doctor.specialty)}
          {doctor.years_experience != null && ` · ${t("doctors.years", { count: formatNumber(doctor.years_experience) })}`}
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs">
          {doctor.rating != null && (
            <span className="flex items-center gap-1 font-semibold text-gold">
              <Star className="h-3.5 w-3.5 fill-gold-star text-gold-star" aria-hidden="true" />
              {formatNumber(Number(doctor.rating), 1)}
            </span>
          )}
          {nextSlot && (
            <span className="flex items-center gap-1 font-semibold text-sage">
              <CalendarClock className="h-3.5 w-3.5" aria-hidden="true" />
              {t("doctors.nextAvailable", {
                date: `${formatDate(new Date(nextSlot.start_time))} · ${formatTime(new Date(nextSlot.start_time))}`,
              })}
            </span>
          )}
          {priceFrom != null && (
            <span className="text-ink-muted">{t("doctors.priceFrom", { price: formatCurrency(priceFrom) })}</span>
          )}
        </div>
      </div>
    </Link>
  );
}
