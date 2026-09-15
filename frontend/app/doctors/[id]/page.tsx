"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { ShieldCheck, Star, Calendar, GraduationCap } from "lucide-react";
import { useDoctor } from "@/hooks/use-doctor";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";

export default function DoctorDetailPage() {
  const params = useParams<{ id: string }>();
  const { data: doctor, isLoading, isError, refetch } = useDoctor(params.id);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12 md:px-6">
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (isError || !doctor) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12 md:px-6">
        <ErrorState message="لم نتمكن من العثور على هذا الطبيب." onRetry={() => refetch()} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-12 md:px-6">
      <div className="flex flex-col gap-6 rounded-3xl border border-border bg-surface p-8">
        <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <h1 className="text-2xl font-bold text-ink md:text-3xl">{doctor.full_name}</h1>
            <p className="mt-1 text-ink-muted">{doctor.specialty}</p>
          </div>
          {doctor.verification_status === "verified" && (
            <Badge tone="sage">
              <ShieldCheck className="h-4 w-4" />
              طبيب موثّق
            </Badge>
          )}
        </div>

        <div className="flex flex-wrap gap-6 text-sm text-ink-muted">
          {doctor.rating != null && (
            <span className="flex items-center gap-1.5">
              <Star className="h-4 w-4 fill-gold text-gold" />
              <span className="text-ink">{Number(doctor.rating).toFixed(1)}</span> تقييم المرضى
            </span>
          )}
          {doctor.years_experience != null && (
            <span className="flex items-center gap-1.5">
              <GraduationCap className="h-4 w-4" />
              {doctor.years_experience} سنوات خبرة
            </span>
          )}
        </div>

        {doctor.bio && (
          <div>
            <p className="mb-1 font-semibold text-ink">نبذة عن الطبيب</p>
            <p className="leading-relaxed text-ink-muted">{doctor.bio}</p>
          </div>
        )}

        <div className="flex flex-col gap-3 border-t border-border pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-ink-muted">جاهزة لحجز استشارتك؟</p>
          <Link href={`/booking?doctorId=${doctor.id}`}>
            <Button size="lg">
              <Calendar className="h-4 w-4" />
              احجزي مع {doctor.full_name.split(" ")[0]}
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
