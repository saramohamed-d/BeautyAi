"use client";

import { useMemo } from "react";
import { Building2, MapPin } from "lucide-react";
import { useAvailability } from "@/hooks/use-availability";
import { useClinics } from "@/hooks/use-clinics";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import type { Clinic } from "@/types/clinic";
import { cn } from "@/lib/utils";

/**
 * Clinics a doctor practices at are derived from their actual
 * availability data (distinct clinic_id values), rather than a
 * dedicated "doctor's clinics" endpoint — Sprint 2 doesn't expose one,
 * and adding a new backend endpoint for a frontend sprint isn't
 * justified when the same information already flows through the
 * availability API. See docs/api.md — this is documented, not a hack.
 */
export function ClinicSelectStep({
  doctorId,
  selectedClinic,
  onSelect,
}: {
  doctorId: string;
  selectedClinic: Clinic | null;
  onSelect: (clinic: Clinic) => void;
}) {
  const { data: availabilityData, isLoading: availabilityLoading } = useAvailability({
    doctor_id: doctorId,
    is_booked: false,
    page_size: 100,
  });
  const { data: clinicsData, isLoading: clinicsLoading } = useClinics({ page_size: 100 });

  const doctorClinics = useMemo(() => {
    if (!availabilityData || !clinicsData) return [];
    const clinicIds = new Set(availabilityData.items.map((slot) => slot.clinic_id));
    return clinicsData.items.filter((clinic) => clinicIds.has(clinic.id));
  }, [availabilityData, clinicsData]);

  const isLoading = availabilityLoading || clinicsLoading;

  if (isLoading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        {Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-20" />)}
      </div>
    );
  }

  if (doctorClinics.length === 0) {
    return (
      <EmptyState
        icon={Building2}
        title="لا توجد مواعيد متاحة لهذا الطبيب حالياً"
        description="جرّبي اختيار طبيب آخر أو راجعي لاحقاً."
      />
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {doctorClinics.map((clinic) => {
        const isSelected = selectedClinic?.id === clinic.id;
        return (
          <button
            key={clinic.id}
            type="button"
            onClick={() => onSelect(clinic)}
            className={cn(
              "flex items-center gap-3 rounded-2xl border p-4 text-right transition-colors",
              isSelected ? "border-primary bg-primary-soft" : "border-border bg-surface hover:border-primary"
            )}
            aria-pressed={isSelected}
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-ink">
              <Building2 className="h-5 w-5" strokeWidth={1.75} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold text-ink">{clinic.name}</p>
              <p className="flex items-center gap-1 truncate text-sm text-ink-muted">
                <MapPin className="h-3 w-3" /> {clinic.city}
              </p>
            </div>
          </button>
        );
      })}
    </div>
  );
}
