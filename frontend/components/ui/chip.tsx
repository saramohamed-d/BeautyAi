import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes } from "react";

/** Filter chip (the demo's `.chip`); pink when active. */
export function Chip({ active = false, className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={cn(
        "shrink-0 whitespace-nowrap rounded-xl border px-3 py-2 text-xs font-semibold transition-colors",
        active ? "border-primary-accent bg-primary-soft text-primary-dark" : "border-border bg-surface text-ink hover:border-primary-line",
        className
      )}
      {...props}
    />
  );
}
