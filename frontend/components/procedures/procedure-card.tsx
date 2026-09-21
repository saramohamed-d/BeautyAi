"use client";

import Link from "next/link";
import { Sparkle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/lib/i18n/provider";
import type { Procedure } from "@/types/procedure";

export function ProcedureCard({ procedure }: { procedure: Procedure }) {
  const { t, label, formatCurrency } = useI18n();
  const hasPrice = procedure.typical_price_min != null || procedure.typical_price_max != null;

  return (
    <Link
      href={`/procedures/${procedure.id}`}
      className="flex items-center gap-[11px] rounded-card border border-border bg-surface p-3 transition-colors hover:border-primary-line"
    >
      <div className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-lavender-soft text-ink">
        <Sparkle className="h-5 w-5" strokeWidth={1.75} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-bold text-ink">{procedure.name}</p>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <Badge tone="lavender">{label("categories", procedure.category)}</Badge>
          {hasPrice && (
            <span className="text-xs text-ink-muted">
              {t("procedures.priceRange", {
                min: formatCurrency(procedure.typical_price_min),
                max: formatCurrency(procedure.typical_price_max),
              })}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
