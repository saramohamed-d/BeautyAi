import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Shown whenever a query fails — including when the backend is entirely
 * unreachable. The app should never crash on this; every list/detail
 * page wires its query's `isError` state to this component.
 */
export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-border bg-surface px-6 py-16 text-center">
      <AlertTriangle className="h-8 w-8 text-primary" strokeWidth={1.5} />
      <p className="text-lg font-semibold text-ink">تعذر تحميل البيانات</p>
      <p className="max-w-sm text-sm text-ink-muted">
        {message ?? "حدث خطأ أثناء الاتصال بالخادم. تأكدي من اتصالك بالإنترنت وحاولي مرة أخرى."}
      </p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          إعادة المحاولة
        </Button>
      )}
    </div>
  );
}
