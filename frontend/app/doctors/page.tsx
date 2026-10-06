"use client";

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Search, UserRound } from "lucide-react";
import { Page } from "@/components/layout/page";
import { DoctorCard } from "@/components/doctors/doctor-card";
import { Chip } from "@/components/ui/chip";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useDoctorSearch } from "@/hooks/use-doctor-search";
import { useDebounced } from "@/hooks/use-debounced";
import { useI18n } from "@/lib/i18n/provider";

const SPECIALTIES = ["Dermatology", "Aesthetic Medicine"];
type Sort = "soonest" | "rating" | "price";

const selectClass =
  "h-10 rounded-full border border-border bg-surface px-4 text-sm font-semibold text-ink outline-none focus:border-primary-accent";

function DoctorsPageContent() {
  const { t, label } = useI18n();
  const searchParams = useSearchParams();
  const [specialty, setSpecialty] = useState(searchParams.get("specialty") ?? "");
  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const [city, setCity] = useState("");
  const [sort, setSort] = useState<Sort>("soonest");

  const q = useDebounced(query.trim());

  // Verified doctors only (GET /doctors/search), sorted by the API.
  const { data, isLoading, isError, refetch } = useDoctorSearch({
    page_size: 50,
    q: q || undefined,
    specialty: specialty || undefined,
    city: city || undefined,
    sort,
  });

  // Cities offered in the filter: every city a listed doctor works in (or the one already picked).
  const { data: allData } = useDoctorSearch({ page_size: 50 });
  const cities = useMemo(() => {
    const names = new Set((allData?.items ?? []).flatMap((item) => item.clinics.map((clinic) => clinic.city)));
    if (city) names.add(city);
    return [...names].sort();
  }, [allData, city]);

  const results = data?.items ?? [];

  return (
    <Page>
      <h1 className="font-display text-[28px] font-semibold leading-tight text-ink md:text-4xl">{t("doctors.title")}</h1>
      <p className="mt-1 text-sm text-ink-muted">{t("doctors.subtitle")}</p>

      <div className="no-scrollbar mt-5 flex gap-2 overflow-x-auto">
        <Chip active={!specialty} onClick={() => setSpecialty("")}>
          {t("doctors.all")}
        </Chip>
        {SPECIALTIES.map((s) => (
          <Chip key={s} active={specialty === s} onClick={() => setSpecialty(s)}>
            {label("specialties", s)}
          </Chip>
        ))}
      </div>

      <div className="mt-4 flex flex-col gap-3 md:flex-row md:items-center">
        <div className="flex h-11 shrink-0 items-center gap-2 rounded-full md:flex-1 border border-border bg-surface px-4 md:max-w-sm">
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
        <div className="flex flex-wrap items-center gap-2 md:ms-auto">
          <label className="flex items-center gap-2 text-sm text-ink-muted">
            {t("doctors.location")}
            <select value={city} onChange={(e) => setCity(e.target.value)} className={selectClass}>
              <option value="">{t("doctors.anyCity")}</option>
              {cities.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm text-ink-muted">
            {t("doctors.sortBy")}
            <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} className={selectClass}>
              <option value="soonest">{t("doctors.sortSoonest")}</option>
              <option value="rating">{t("doctors.sortRating")}</option>
              <option value="price">{t("doctors.sortPrice")}</option>
            </select>
          </label>
        </div>
      </div>

      <div className="mt-5">
        {isLoading && (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[112px]" />)}
          </div>
        )}

        {isError && <ErrorState onRetry={() => refetch()} />}

        {!isLoading && !isError && results.length === 0 && (
          <EmptyState icon={UserRound} title={t("doctors.emptyTitle")} description={t("doctors.emptyBody")} />
        )}

        {!isLoading && !isError && results.length > 0 && (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {results.map(({ doctor, next_slot, price_from, clinics }) => (
              <DoctorCard key={doctor.id} doctor={doctor} nextSlot={next_slot} priceFrom={price_from} clinics={clinics} />
            ))}
          </div>
        )}
      </div>
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
