"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { MapPin, Phone, Mail, Calendar } from "lucide-react";
import { useClinic } from "@/hooks/use-clinic";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";

export default function ClinicDetailPage() {
  const params = useParams<{ id: string }>();
  const { data: clinic, isLoading, isError, refetch } = useClinic(params.id);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12 md:px-6">
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (isError || !clinic) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12 md:px-6">
        <ErrorState message="لم نتمكن من العثور على هذه العيادة." onRetry={() => refetch()} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-12 md:px-6">
      <div className="flex flex-col gap-6 rounded-3xl border border-border bg-surface p-8">
        <div>
          <h1 className="text-2xl font-bold text-ink md:text-3xl">{clinic.name}</h1>
          <p className="mt-1 flex items-center gap-1.5 text-ink-muted">
            <MapPin className="h-4 w-4" />
            {clinic.address ? `${clinic.address}, ` : ""}{clinic.city}، {clinic.country}
          </p>
        </div>

        {clinic.description && <p className="leading-relaxed text-ink-muted">{clinic.description}</p>}

        <div className="flex flex-wrap gap-6 text-sm text-ink-muted">
          {clinic.phone && (
            <span className="flex items-center gap-1.5"><Phone className="h-4 w-4" /> {clinic.phone}</span>
          )}
          {clinic.email && (
            <span className="flex items-center gap-1.5"><Mail className="h-4 w-4" /> {clinic.email}</span>
          )}
        </div>

        <div className="flex flex-col gap-3 border-t border-border pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-ink-muted">اختاري طبيبك لحجز موعد في إحدى عياداتنا</p>
          <Link href="/doctors">
            <Button size="lg">
              <Calendar className="h-4 w-4" />
              تصفّحي الأطباء
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
