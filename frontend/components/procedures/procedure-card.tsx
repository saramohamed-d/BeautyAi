import Link from "next/link";
import { Sparkle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatCurrency } from "@/lib/format";
import type { Procedure } from "@/types/procedure";

export function ProcedureCard({ procedure }: { procedure: Procedure }) {
  const hasPriceRange = procedure.typical_price_min != null || procedure.typical_price_max != null;

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary-dark">
          <Sparkle className="h-5 w-5" strokeWidth={1.75} />
        </div>
        <div>
          <p className="font-semibold text-ink">{procedure.name}</p>
          <Badge tone="neutral" className="mt-1">{procedure.category}</Badge>
        </div>
      </div>

      {procedure.description && <p className="line-clamp-2 text-sm text-ink-muted">{procedure.description}</p>}

      <div className="flex items-center justify-between">
        {hasPriceRange ? (
          <p className="text-sm text-ink-muted">
            من {formatCurrency(procedure.typical_price_min)} إلى {formatCurrency(procedure.typical_price_max)}
          </p>
        ) : (
          <span />
        )}
        <Link href={`/procedures/${procedure.id}`}>
          <Button variant="secondary" size="sm">التفاصيل</Button>
        </Link>
      </div>
    </Card>
  );
}
