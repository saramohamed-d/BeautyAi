"use client";

import { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Sparkle } from "lucide-react";
import { ProcedureCard } from "@/components/procedures/procedure-card";
import { SectionHeading } from "@/components/ui/section-heading";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Select } from "@/components/ui/select";
import { useProcedures } from "@/hooks/use-procedures";

const CATEGORIES = [
  { value: "injectable", label: "الحقن التجميلي" },
  { value: "laser", label: "الليزر" },
  { value: "skin_treatment", label: "العناية بالبشرة" },
];

function ProceduresPageContent() {
  const searchParams = useSearchParams();
  const [category, setCategory] = useState(searchParams.get("category") ?? "");

  useEffect(() => {
    const fromUrl = searchParams.get("category");
    if (fromUrl) setCategory(fromUrl);
  }, [searchParams]);

  const { data, isLoading, isError, refetch } = useProcedures({ page_size: 24, category: category || undefined });

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 md:px-6">
      <SectionHeading
        eyebrow="اكتشفي"
        title="الإجراءات التجميلية والجلدية"
        description="تصفّحي الإجراءات المتاحة وأسعارها التقريبية قبل اختيار طبيبك."
      />

      <div className="mt-6 max-w-xs">
        <Select label="التصنيف" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">كل التصنيفات</option>
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </Select>
      </div>

      {isLoading && (
        <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-44" />)}
        </div>
      )}

      {isError && <div className="mt-8"><ErrorState onRetry={() => refetch()} /></div>}

      {!isLoading && !isError && data && data.items.length === 0 && (
        <div className="mt-8">
          <EmptyState icon={Sparkle} title="لا توجد إجراءات في هذا التصنيف" description="جرّبي تصنيفاً آخر." />
        </div>
      )}

      {!isLoading && !isError && data && data.items.length > 0 && (
        <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {data.items.map((procedure) => (
            <ProcedureCard key={procedure.id} procedure={procedure} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function ProceduresPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-6xl px-4 py-12 md:px-6"><Skeleton className="h-44" /></div>}>
      <ProceduresPageContent />
    </Suspense>
  );
}
