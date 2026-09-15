import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

/**
 * Base card: hairline border, not a grey box-shadow — keeps the flatter,
 * boutique feel the design brief calls for instead of the generic
 * "SaaS card kit" look (uniform shadow under every card).
 */
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-2xl border border-border bg-surface p-5", className)}
      {...props}
    />
  );
}
