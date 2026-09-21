"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Search, UserRound } from "lucide-react";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { DoctorCard } from "@/components/doctors/doctor-card";
import { Chip } from "@/components/ui/chip";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useDoctorSearch } from "@/hooks/use-doctor-search";
import { useDebounced } from "@/hooks/use-debounced";
import { useI18n } from "@/lib/i18n/provider";

const SPECIALTIES = ["Dermatology", "Aesthetic Medicine"];

function DoctorsPageContent() {
  const { t, label } = useI18n();
  const searchParams = useSearchParams();
  const [specialty, setSpecialty] = useState(searchParams.get("specialty") ?? "");
  const [query, setQuery] = useState(searchParams.get("q") ?? "");

  const q = useDebounced(query.trim());

  // Verified doctors only, soonest availability first (GET /doctors/search).
  const { data, isLoading, isError, refetch } = useDoctorSearch({
    page_size: 50,
    q: q || undefined,
    specialty: specialty || undefined,
  });
  const results = data?.items ?? [];

  return (
    <Page>
      <PageHeader title={t("doctors.title")} backHref="/" />

      <div className="my-[18px] flex h-12 items-center gap-2 rounded-tile border border-border bg-surface px-[14px] md:max-w-xl">
        <Search className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden="true" />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("doctors.searchPlaceholder")}
          aria-label={t("doctors.searchPlaceholder")}
          className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-ink-muted/80"
        />
      </div>

      <div className="no-scrollbar mb-3 flex gap-[7px] overflow-x-auto">
        <Chip active={!specialty} onClick={() => setSpecialty("")}>
          {t("doctors.all")}
        </Chip>
        {SPECIALTIES.map((s) => (
          <Chip key={s} active={specialty === s} onClick={() => setSpecialty(s)}>
            {label("specialties", s)}
          </Chip>
        ))}
      </div>

      {isLoading && (
        <div className="grid gap-2.5 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[76px]" />)}
        </div>
      )}

      {isError && <ErrorState onRetry={() => refetch()} />}

      {!isLoading && !isError && results.length === 0 && (
        <EmptyState icon={UserRound} title={t("doctors.emptyTitle")} description={t("doctors.emptyBody")} />
      )}

      {!isLoading && !isError && results.length > 0 && (
        <div className="grid gap-2.5 md:grid-cols-2">
          {results.map(({ doctor, next_slot, price_from }) => (
            <DoctorCard key={doctor.id} doctor={doctor} nextSlot={next_slot} priceFrom={price_from} />
          ))}
        </div>
      )}
    </Page>
  );
}

export default function DoctorsPage() {
  return (
    <Suspense fallback={<Page><Skeleton className="h-48" /></Page>}>
      <DoctorsPageContent />
    </Suspense>
  );
}
