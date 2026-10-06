import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

/** Base card: white, hairline border, soft pink shadow, 18px radius. */
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-card border border-border bg-surface p-[14px] shadow-card", className)} {...props} />;
}
