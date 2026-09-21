"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Sparkle } from "lucide-react";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { ProcedureCard } from "@/components/procedures/procedure-card";
import { Chip } from "@/components/ui/chip";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useProcedures } from "@/hooks/use-procedures";
import { useI18n } from "@/lib/i18n/provider";

const CATEGORIES = ["injectable", "laser", "skin_treatment"];

function ProceduresPageContent() {
  const { t, label } = useI18n();
  const searchParams = useSearchParams();
  const [category, setCategory] = useState(searchParams.get("category") ?? "");

  useEffect(() => {
    const fromUrl = searchParams.get("category");
    if (fromUrl) setCategory(fromUrl);
  }, [searchParams]);

  const { data, isLoading, isError, refetch } = useProcedures({ page_size: 50, category: category || undefined });

  return (
    <Page>
      <PageHeader title={t("procedures.title")} backHref="/" />

      <div className="no-scrollbar mb-3 flex gap-[7px] overflow-x-auto">
        <Chip active={!category} onClick={() => setCategory("")}>
          {t("procedures.all")}
        </Chip>
        {CATEGORIES.map((c) => (
          <Chip key={c} active={category === c} onClick={() => setCategory(c)}>
            {label("categories", c)}
          </Chip>
        ))}
      </div>

      {isLoading && (
        <div className="grid gap-2.5 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[76px]" />)}
        </div>
      )}

      {isError && <ErrorState onRetry={() => refetch()} />}

      {!isLoading && !isError && data?.items.length === 0 && (
        <EmptyState icon={Sparkle} title={t("procedures.emptyTitle")} description={t("procedures.emptyBody")} />
      )}

      {!isLoading && !isError && data && data.items.length > 0 && (
        <div className="grid gap-2.5 md:grid-cols-2">
          {data.items.map((procedure) => (
            <ProcedureCard key={procedure.id} procedure={procedure} />
          ))}
        </div>
      )}
    </Page>
  );
}

export default function ProceduresPage() {
  return (
    <Suspense fallback={<Page><Skeleton className="h-48" /></Page>}>
      <ProceduresPageContent />
    </Suspense>
  );
}
