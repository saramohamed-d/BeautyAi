"use client";

import { useState } from "react";
import { Search, ShieldCheck, Stethoscope } from "lucide-react";
import { useDoctors } from "@/hooks/use-doctors";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import type { Doctor } from "@/types/doctor";
import { cn } from "@/lib/utils";

export function DoctorSelectStep({
  selectedDoctor,
  onSelect,
}: {
  selectedDoctor: Doctor | null;
  onSelect: (doctor: Doctor) => void;
}) {
  const [specialty, setSpecialty] = useState("");
  const { data, isLoading } = useDoctors({ page_size: 50, is_active: true, specialty: specialty || undefined });

  return (
    <div className="flex flex-col gap-4">
      <div className="relative max-w-sm">
        <Search className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" />
        <Input
          placeholder="ابحثي بالتخصص، مثال: Dermatology"
          value={specialty}
          onChange={(e) => setSpecialty(e.target.value)}
          className="pr-10"
        />
      </div>

      {isLoading && (
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-20" />)}
        </div>
      )}

      {!isLoading && data?.items.length === 0 && (
        <EmptyState icon={Stethoscope} title="لا يوجد أطباء مطابقون" description="جرّبي تخصصاً آخر." />
      )}

      {!isLoading && data && data.items.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {data.items.map((doctor) => {
            const isSelected = selectedDoctor?.id === doctor.id;
            return (
              <button
                key={doctor.id}
                type="button"
                onClick={() => onSelect(doctor)}
                className={cn(
                  "flex items-center gap-3 rounded-2xl border p-4 text-right transition-colors",
                  isSelected ? "border-primary bg-primary-soft" : "border-border bg-surface hover:border-primary"
                )}
                aria-pressed={isSelected}
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-primary-dark">
                  <Stethoscope className="h-5 w-5" strokeWidth={1.75} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold text-ink">{doctor.full_name}</p>
                  <p className="truncate text-sm text-ink-muted">{doctor.specialty}</p>
                </div>
                {doctor.verification_status === "verified" && (
                  <ShieldCheck className="h-4 w-4 shrink-0 text-sage" />
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
