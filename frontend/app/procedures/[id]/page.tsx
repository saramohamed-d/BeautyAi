"use client";

import { useParams } from "next/navigation";
import { Info, Sparkle } from "lucide-react";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { useProcedure } from "@/hooks/use-procedure";
import { useI18n } from "@/lib/i18n/provider";

export default function ProcedureDetailPage() {
  const { t, label, formatCurrency } = useI18n();
  const params = useParams<{ id: string }>();
  const { data: procedure, isLoading, isError, refetch } = useProcedure(params.id);
  const hasPrice = procedure && (procedure.typical_price_min != null || procedure.typical_price_max != null);

  return (
    <Page width="narrow">
      <PageHeader title={t("procedures.detailTitle")} />

      {isLoading && <Skeleton className="h-64" />}
      {(isError || (!isLoading && !procedure)) && <ErrorState message={t("errors.procedureNotFound")} onRetry={() => refetch()} />}

      {procedure && (
        <>
          <div className="text-center">
            <div className="mx-auto my-6 grid h-[82px] w-[82px] place-items-center rounded-[28px] bg-lavender-soft text-ink">
              <Sparkle className="h-9 w-9" strokeWidth={1.5} />
            </div>
            <h2 className="text-xl font-bold text-ink">{procedure.name}</h2>
            <Badge tone="lavender" className="mt-2">{label("categories", procedure.category)}</Badge>
          </div>

          {procedure.description && (
            <Card className="mt-5">
              <p className="text-sm leading-relaxed text-ink-muted">{procedure.description}</p>
            </Card>
          )}

          {hasPrice && (
            <Card className="mt-2.5 flex items-center justify-between">
              <span className="text-sm text-ink-muted">{t("procedures.typicalPrice")}</span>
              <span className="text-sm font-bold text-primary-dark">
                {t("procedures.priceRange", {
                  min: formatCurrency(procedure.typical_price_min),
                  max: formatCurrency(procedure.typical_price_max),
                })}
              </span>
            </Card>
          )}

          <Notice className="mt-2.5 flex gap-2">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-primary-dark" aria-hidden="true" />
            <p>{t("procedures.priceNote")}</p>
          </Notice>

          <LinkButton href="/doctors" block className="mt-[15px]">
            {t("procedures.chooseDoctor")}
          </LinkButton>
        </>
      )}
    </Page>
  );
}
