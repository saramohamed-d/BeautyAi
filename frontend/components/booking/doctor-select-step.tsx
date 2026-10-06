"use client";

import { useState } from "react";
import { Search, ShieldCheck, Stethoscope } from "lucide-react";
import { DoctorAvatar } from "@/components/doctors/doctor-avatar";
import { SelectableCard } from "@/components/ui/selectable-card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useDoctors } from "@/hooks/use-doctors";
import { useI18n } from "@/lib/i18n/provider";
import type { Doctor } from "@/types/doctor";

export function DoctorSelectStep({
  selectedDoctor,
  onSelect,
}: {
  selectedDoctor: Doctor | null;
  onSelect: (doctor: Doctor) => void;
}) {
  const { t, label } = useI18n();
  const [specialty, setSpecialty] = useState("");
  const { data, isLoading } = useDoctors({ page_size: 50, is_active: true, specialty: specialty.trim() || undefined });

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex h-12 items-center gap-2 rounded-tile border border-border bg-surface px-[14px]">
        <Search className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden="true" />
        <input
          type="search"
          value={specialty}
          onChange={(e) => setSpecialty(e.target.value)}
          placeholder={t("booking.searchSpecialty")}
          aria-label={t("booking.searchSpecialty")}
          className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-ink-muted/80"
        />
      </div>

      {isLoading && Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-[76px]" />)}

      {!isLoading && data?.items.length === 0 && (
        <EmptyState icon={Stethoscope} title={t("booking.noDoctorsTitle")} description={t("booking.noDoctorsBody")} />
      )}

      {data?.items.map((doctor) => (
        <SelectableCard key={doctor.id} selected={selectedDoctor?.id === doctor.id} onClick={() => onSelect(doctor)}>
          <DoctorAvatar avatar={doctor.avatar} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-bold text-ink">{doctor.full_name}</p>
            <p className="truncate text-xs text-ink-muted">{label("specialties", doctor.specialty)}</p>
          </div>
          {doctor.verification_status === "verified" && (
            <ShieldCheck className="h-4 w-4 shrink-0 text-sage" aria-label={t("common.verified")} />
          )}
        </SelectableCard>
      ))}
    </div>
  );
}
