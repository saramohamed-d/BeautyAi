"use client";

import { Building2, MapPin } from "lucide-react";
import { SelectableCard } from "@/components/ui/selectable-card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useDoctorClinics } from "@/hooks/use-doctor-clinics";
import { useI18n } from "@/lib/i18n/provider";
import type { Clinic } from "@/types/clinic";

export function ClinicSelectStep({
  doctorId,
  selectedClinic,
  onSelect,
}: {
  doctorId: string;
  selectedClinic: Clinic | null;
  onSelect: (clinic: Clinic) => void;
}) {
  const { t } = useI18n();
  const { clinics, isLoading } = useDoctorClinics(doctorId);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-2.5">
        {Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-[72px]" />)}
      </div>
    );
  }

  if (clinics.length === 0) {
    return <EmptyState icon={Building2} title={t("booking.noClinicsTitle")} description={t("booking.noClinicsBody")} />;
  }

  return (
    <div className="flex flex-col gap-2.5">
      {clinics.map((clinic) => (
        <SelectableCard key={clinic.id} selected={selectedClinic?.id === clinic.id} onClick={() => onSelect(clinic)}>
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-sage-soft text-sage">
            <Building2 className="h-5 w-5" strokeWidth={1.75} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-bold text-ink">{clinic.name}</p>
            <p className="flex items-center gap-1 truncate text-xs text-ink-muted">
              <MapPin className="h-3 w-3 shrink-0" />
              {clinic.address ? `${clinic.address} · ` : ""}
              {clinic.city}
            </p>
          </div>
        </SelectableCard>
      ))}
    </div>
  );
}
