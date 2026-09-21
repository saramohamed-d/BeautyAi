import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

/**
 * Empty/unavailable state. An empty screen is an invitation to act —
 * pass an `action` wherever there is a sensible next step.
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
    <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-border bg-surface/60 px-6 py-12 text-center">
      <div className="mb-1 grid h-14 w-14 place-items-center rounded-[20px] bg-primary-soft text-primary-dark">
        <Icon className="h-6 w-6" strokeWidth={1.75} />
      </div>
      <p className="font-bold text-ink">{title}</p>
      {description && <p className="max-w-xs text-sm text-ink-muted">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
