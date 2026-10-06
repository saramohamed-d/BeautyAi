import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

/** Blush gradient callout for guidance and disclaimers. */
export function Notice({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-[17px] bg-gradient-to-br from-blush to-surface p-[14px] text-sm leading-relaxed text-ink", className)}
      {...props}
    />
  );
}
