"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { UserRound } from "lucide-react";
import { DoctorCard } from "@/components/doctors/doctor-card";
import { SectionHeading } from "@/components/ui/section-heading";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Select } from "@/components/ui/select";
import { useDoctors } from "@/hooks/use-doctors";

const SPECIALTIES = ["Dermatology", "Aesthetic Medicine"];

function DoctorsPageContent() {
  const searchParams = useSearchParams();
  const [specialty, setSpecialty] = useState(searchParams.get("specialty") ?? "");

  const { data, isLoading, isError, refetch } = useDoctors({
    page_size: 24,
    is_active: true,
    specialty: specialty || undefined,
  });

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 md:px-6">
      <SectionHeading
        eyebrow="اكتشفي"
        title="الأطباء الموثّقون"
        description="تصفّحي أطباء التجميل والجلدية المعتمدين على منصة BeautyAI واحجزي استشارتك."
      />

      <div className="mt-6 max-w-xs">
        <Select label="التخصص" value={specialty} onChange={(e) => setSpecialty(e.target.value)}>
          <option value="">كل التخصصات</option>
          {SPECIALTIES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </Select>
      </div>

      {isLoading && (
        <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-48" />)}
        </div>
      )}

      {isError && <div className="mt-8"><ErrorState onRetry={() => refetch()} /></div>}

      {!isLoading && !isError && data && data.items.length === 0 && (
        <div className="mt-8">
          <EmptyState
            icon={UserRound}
            title="لا يوجد أطباء مطابقون"
            description="جرّبي تغيير التخصص أو تصفّحي كل الأطباء المتاحين."
          />
        </div>
      )}

      {!isLoading && !isError && data && data.items.length > 0 && (
        <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {data.items.map((doctor) => (
            <DoctorCard key={doctor.id} doctor={doctor} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function DoctorsPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-6xl px-4 py-12 md:px-6"><Skeleton className="h-48" /></div>}>
      <DoctorsPageContent />
    </Suspense>
  );
}
