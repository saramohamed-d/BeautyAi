"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { GraduationCap, MapPin, ShieldCheck, Star } from "lucide-react";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { DoctorAvatar } from "@/components/doctors/doctor-avatar";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { useDoctor } from "@/hooks/use-doctor";
import { useDoctorClinics } from "@/hooks/use-doctor-clinics";
import { useI18n } from "@/lib/i18n/provider";

export default function DoctorDetailPage() {
  const { t, label, formatNumber } = useI18n();
  const params = useParams<{ id: string }>();
  const { data: doctor, isLoading, isError, refetch } = useDoctor(params.id);
  const { clinics, isLoading: clinicsLoading } = useDoctorClinics(params.id);

  return (
    <Page width="narrow">
      <PageHeader title={t("doctors.profileTitle")} />

      {isLoading && <Skeleton className="h-72" />}
      {(isError || (!isLoading && !doctor)) && <ErrorState message={t("errors.doctorNotFound")} onRetry={() => refetch()} />}

      {doctor && (
        <>
          <div className="rounded-card bg-gradient-to-b from-blush to-transparent px-4 pb-2 pt-6 text-center">
            <DoctorAvatar avatar={doctor.avatar} size="xl" className="mx-auto mb-4 shadow-card" />
            <h2 className="font-display text-2xl font-semibold text-ink">{doctor.full_name}</h2>
            <p className="mt-1 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-xs text-ink-muted">
              <span>{label("specialties", doctor.specialty)}</span>
              {doctor.rating != null && (
                <span className="flex items-center gap-1 font-semibold text-gold">
                  <Star className="h-3.5 w-3.5 fill-gold-star text-gold-star" aria-hidden="true" />
                  {t("common.rating", { rating: formatNumber(Number(doctor.rating), 1) })}
                </span>
              )}
              {doctor.years_experience != null && (
                <span className="flex items-center gap-1">
                  <GraduationCap className="h-3.5 w-3.5" aria-hidden="true" />
                  {t("doctors.years", { count: formatNumber(doctor.years_experience) })}
                </span>
              )}
            </p>
            {doctor.verification_status === "verified" && (
              <Badge tone="sage" className="mt-3">
                <ShieldCheck className="h-3.5 w-3.5" /> {t("common.verified")}
              </Badge>
            )}
          </div>

          {doctor.bio && (
            <Card className="mt-5">
              <p className="text-sm font-bold text-ink">{t("doctors.about")}</p>
              <p className="mt-1 text-sm leading-relaxed text-ink-muted">{doctor.bio}</p>
            </Card>
          )}

          <Card className="mt-2.5">
            <p className="text-sm font-bold text-ink">{t("doctors.where")}</p>
            {clinicsLoading ? (
              <Skeleton className="mt-2 h-10" />
            ) : clinics.length === 0 ? (
              <p className="mt-1 text-sm text-ink-muted">{t("doctors.noSlots")}</p>
            ) : (
              <ul className="mt-1">
                {clinics.map((clinic) => (
                  <li key={clinic.id}>
                    <Link href={`/clinics/${clinic.id}`} className="flex items-center gap-1.5 py-1.5 text-sm text-ink hover:text-primary-dark">
                      <MapPin className="h-4 w-4 shrink-0 text-primary-dark" />
                      {clinic.name} · <span className="text-ink-muted">{clinic.city}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <LinkButton href={`/booking?doctorId=${doctor.id}`} block className="mt-[15px]">
            {t("doctors.book")}
          </LinkButton>
        </>
      )}
    </Page>
  );
}
