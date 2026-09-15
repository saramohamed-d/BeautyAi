"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { Calendar } from "lucide-react";
import { useProcedure } from "@/hooks/use-procedure";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { formatCurrency } from "@/lib/format";

export default function ProcedureDetailPage() {
  const params = useParams<{ id: string }>();
  const { data: procedure, isLoading, isError, refetch } = useProcedure(params.id);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12 md:px-6">
        <Skeleton className="h-56" />
      </div>
    );
  }

  if (isError || !procedure) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12 md:px-6">
        <ErrorState message="لم نتمكن من العثور على هذا الإجراء." onRetry={() => refetch()} />
      </div>
    );
  }

  const hasPriceRange = procedure.typical_price_min != null || procedure.typical_price_max != null;

  return (
    <div className="mx-auto max-w-4xl px-4 py-12 md:px-6">
      <div className="flex flex-col gap-6 rounded-3xl border border-border bg-surface p-8">
        <div>
          <Badge tone="neutral">{procedure.category}</Badge>
          <h1 className="mt-3 text-2xl font-bold text-ink md:text-3xl">{procedure.name}</h1>
        </div>

        {procedure.description && <p className="leading-relaxed text-ink-muted">{procedure.description}</p>}

        {hasPriceRange && (
          <p className="text-sm text-ink-muted">
            السعر التقريبي: من {formatCurrency(procedure.typical_price_min)} إلى {formatCurrency(procedure.typical_price_max)}
          </p>
        )}

        <p className="rounded-xl bg-primary-soft px-4 py-3 text-sm text-primary-dark">
          الأسعار الفعلية قد تختلف حسب الطبيب والعيادة. سيتم عرض السعر الدقيق عند اختيار طبيبك أثناء الحجز.
        </p>

        <div className="flex flex-col gap-3 border-t border-border pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-ink-muted">جاهزة تحجزي هذا الإجراء؟</p>
          <Link href="/doctors">
            <Button size="lg">
              <Calendar className="h-4 w-4" />
              اختاري طبيبك
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
