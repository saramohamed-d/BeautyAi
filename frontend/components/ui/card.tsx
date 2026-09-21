import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

/** Base card: white, hairline border, 18px radius — the demo's `.card`. */
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-card border border-border bg-surface p-[14px]", className)} {...props} />;
}
