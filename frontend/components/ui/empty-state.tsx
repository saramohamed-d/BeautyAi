import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

/**
 * Consistent empty/unavailable-state treatment used everywhere a list
 * or feature has nothing to show. Per the design brief: an empty screen
 * is an invitation to act, not just an apology — every use of this
 * component should pass an actionable next step where one exists.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border px-6 py-16 text-center">
      <Icon className="h-8 w-8 text-ink-muted" strokeWidth={1.5} />
      <p className="text-lg font-semibold text-ink">{title}</p>
      {description && <p className="max-w-sm text-sm text-ink-muted">{description}</p>}
      {action}
    </div>
  );
}
