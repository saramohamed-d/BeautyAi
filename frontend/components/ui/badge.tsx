import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

const tones = {
  primary: "bg-primary-soft text-primary-dark",
  gold: "bg-gold-soft text-ink",
  sage: "bg-sage-soft text-sage",
  neutral: "bg-bg text-ink-muted border border-border",
};

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: keyof typeof tones;
}

export function Badge({ className, tone = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn("inline-flex items-center gap-1 rounded-full px-3 py-1 text-sm font-medium", tones[tone], className)}
      {...props}
    />
  );
}
