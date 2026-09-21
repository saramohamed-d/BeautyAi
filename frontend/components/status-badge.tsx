const STYLES: Record<string, string> = {
  ok: "bg-green-100 text-green-800 border-green-300",
  error: "bg-red-100 text-red-800 border-red-300",
  degraded: "bg-amber-100 text-amber-800 border-amber-300",
};

/**
 * Small reusable status pill.
 *
 * Design decision: kept generic (takes any string status + label) rather
 * than hardcoded to "health" concepts, so it can be reused for
 * appointment status, doctor verification status, safety risk level,
 * etc. in later sprints.
 */
export function StatusBadge({ status, label }: { status: string; label: string }) {
  const style = STYLES[status] ?? "bg-gray-100 text-gray-800 border-gray-300";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${style}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {label}
    </span>
  );
}
