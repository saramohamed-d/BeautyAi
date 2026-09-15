"use client";

import { useState } from "react";
import { Building2 } from "lucide-react";
import { ClinicCard } from "@/components/clinics/clinic-card";
import { SectionHeading } from "@/components/ui/section-heading";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { useClinics } from "@/hooks/use-clinics";

export default function ClinicsPage() {
  const [city, setCity] = useState("");
  const { data, isLoading, isError, refetch } = useClinics({ page_size: 24, city: city || undefined });

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 md:px-6">
      <SectionHeading
        eyebrow="اكتشفي"
        title="العيادات المعتمدة"
        description="تصفّحي عيادات التجميل والجلدية الشريكة مع BeautyAI حسب المدينة."
      />

      <div className="mt-6 max-w-xs">
        <Input placeholder="ابحثي عن مدينة، مثال: القاهرة" value={city} onChange={(e) => setCity(e.target.value)} />
      </div>

      {isLoading && (
        <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-40" />)}
        </div>
      )}

      {isError && <div className="mt-8"><ErrorState onRetry={() => refetch()} /></div>}

      {!isLoading && !isError && data && data.items.length === 0 && (
        <div className="mt-8">
          <EmptyState icon={Building2} title="لا توجد عيادات في هذه المدينة" description="جرّبي مدينة أخرى أو امسحي البحث." />
        </div>
      )}

      {!isLoading && !isError && data && data.items.length > 0 && (
        <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {data.items.map((clinic) => (
            <ClinicCard key={clinic.id} clinic={clinic} />
          ))}
        </div>
      )}
    </div>
  );
}
