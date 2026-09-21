"use client";

import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n/provider";

/**
 * Shown whenever a query fails — including when the backend is
 * unreachable. Every list/detail page wires `isError` to this.
 */
export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-col items-center gap-2 rounded-card border border-border bg-surface px-6 py-12 text-center">
      <AlertTriangle className="h-7 w-7 text-primary" strokeWidth={1.75} />
      <p className="font-bold text-ink">{t("errors.loadTitle")}</p>
      <p className="max-w-xs text-sm text-ink-muted">{message ?? t("errors.loadBody")}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" className="mt-2" onClick={onRetry}>
          {t("common.retry")}
        </Button>
      )}
    </div>
  );
}
