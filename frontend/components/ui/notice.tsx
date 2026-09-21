import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

/** Lavender gradient callout (the demo's `.notice`) for guidance and disclaimers. */
export function Notice({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-[17px] bg-gradient-to-br from-lavender-soft to-surface p-[14px] text-sm leading-relaxed text-ink", className)}
      {...props}
    />
  );
}
