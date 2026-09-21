"use client";

import { useState } from "react";
import { Building2, Search } from "lucide-react";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { ClinicCard } from "@/components/clinics/clinic-card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useClinics } from "@/hooks/use-clinics";
import { useI18n } from "@/lib/i18n/provider";

export default function ClinicsPage() {
  const { t } = useI18n();
  const [city, setCity] = useState("");
  const { data, isLoading, isError, refetch } = useClinics({ page_size: 50, city: city.trim() || undefined });

  return (
    <Page>
      <PageHeader title={t("clinics.title")} backHref="/" />

      <div className="my-[18px] flex h-12 items-center gap-2 rounded-tile border border-border bg-surface px-[14px] md:max-w-xl">
        <Search className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden="true" />
        <input
          type="search"
          value={city}
          onChange={(e) => setCity(e.target.value)}
          placeholder={t("clinics.searchPlaceholder")}
          aria-label={t("clinics.searchPlaceholder")}
          className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-ink-muted/80"
        />
      </div>

      {isLoading && (
        <div className="grid gap-2.5 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[76px]" />)}
        </div>
      )}

      {isError && <ErrorState onRetry={() => refetch()} />}

      {!isLoading && !isError && data?.items.length === 0 && (
        <EmptyState icon={Building2} title={t("clinics.emptyTitle")} description={t("clinics.emptyBody")} />
      )}

      {!isLoading && !isError && data && data.items.length > 0 && (
        <div className="grid gap-2.5 md:grid-cols-2">
          {data.items.map((clinic) => (
            <ClinicCard key={clinic.id} clinic={clinic} />
          ))}
        </div>
      )}
    </Page>
  );
}
