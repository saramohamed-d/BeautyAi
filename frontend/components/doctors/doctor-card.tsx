"use client";

import Link from "next/link";
import { CalendarClock, MapPin, ShieldCheck, Star } from "lucide-react";
import { DoctorAvatar } from "@/components/doctors/doctor-avatar";
import { LinkButton } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n/provider";
import type { ClinicSummary, Doctor } from "@/types/doctor";
import type { Availability } from "@/types/availability";

/**
 * Doctor card (the mock-up's "Recommended Doctors" row): avatar, name and
 * specialty, rating and clinic, price and a Book button. The name links
 * to the profile; Book starts booking with this doctor.
 */
export function DoctorCard({
  doctor,
  nextSlot,
  priceFrom,
  clinics = [],
}: {
  doctor: Doctor;
  nextSlot?: Availability | null;
  priceFrom?: number | null;
  clinics?: ClinicSummary[];
}) {
  const { t, label, formatNumber, formatDate, formatTime, formatCurrency } = useI18n();
  const clinic = clinics[0];

  return (
    <article className="relative flex min-w-0 items-center gap-3 rounded-card border border-border bg-surface p-4 shadow-card transition-colors hover:border-primary-line">
      <DoctorAvatar avatar={doctor.avatar} size="lg" className="h-16 w-16 md:h-20 md:w-20" />
      <div className="min-w-0 flex-1">
        <h3 className="flex items-center gap-1.5 text-[15px] font-bold text-ink">
          {/* Stretched link: the whole card opens the profile, the Book button stays its own link. */}
          <Link href={`/doctors/${doctor.id}`} className="truncate after:absolute after:inset-0 after:rounded-card">
            {doctor.full_name}
          </Link>
          {doctor.verification_status === "verified" && (
            <ShieldCheck className="h-4 w-4 shrink-0 text-sage" aria-label={t("common.verified")} />
          )}
        </h3>
        <p className="mt-0.5 truncate text-xs text-ink-muted">
          {label("specialties", doctor.specialty)}
          {doctor.years_experience != null && ` · ${t("doctors.years", { count: formatNumber(doctor.years_experience) })}`}
        </p>
        <div className="mt-1.5 flex flex-col gap-1 text-xs">
          {doctor.rating != null && (
            <span className="flex items-center gap-1 font-semibold text-ink">
              <Star className="h-3.5 w-3.5 fill-gold-star text-gold-star" aria-hidden="true" />
              {formatNumber(Number(doctor.rating), 1)}
            </span>
          )}
          {clinic && (
            <span className="flex items-center gap-1 truncate text-ink-muted">
              <MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              {clinic.name} · {clinic.city}
            </span>
          )}
          {nextSlot && (
            <span className="flex min-w-0 items-center gap-1 truncate font-semibold text-sage">
              <CalendarClock className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              {t("doctors.nextAvailable", {
                date: `${formatDate(new Date(nextSlot.start_time))} · ${formatTime(new Date(nextSlot.start_time))}`,
              })}
            </span>
          )}
        </div>
      </div>
      <div className="relative z-10 flex shrink-0 flex-col items-end gap-2">
        {priceFrom != null && <p className="text-sm font-bold text-ink">{formatCurrency(priceFrom)}</p>}
        <LinkButton href={`/booking?doctorId=${doctor.id}`} size="sm" className="rounded-full px-5">
          {t("doctors.bookShort")}
        </LinkButton>
      </div>
    </article>
  );
}
