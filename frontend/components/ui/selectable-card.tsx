import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/**
 * A full-width choice button (the demo's `.payment` row): white by
 * default, soft pink with a pink outline when selected.
 */
export const SelectableCard = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { selected?: boolean }>(
  ({ className, selected = false, type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      aria-pressed={selected}
      className={cn(
        "flex w-full items-center gap-3 rounded-tile border p-[14px] text-start transition-colors",
        selected ? "border-primary-accent bg-primary-soft" : "border-border bg-surface hover:border-primary-line",
        className
      )}
      {...props}
    />
  )
);
SelectableCard.displayName = "SelectableCard";
