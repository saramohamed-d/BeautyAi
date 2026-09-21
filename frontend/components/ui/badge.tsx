import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

const tones = {
  primary: "bg-primary-soft text-primary-dark",
  gold: "bg-gold-soft text-gold",
  sage: "bg-sage-soft text-sage",
  lavender: "bg-lavender-soft text-ink",
  neutral: "border border-border bg-bg text-ink-muted",
};

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: keyof typeof tones;
}

export function Badge({ className, tone = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold", tones[tone], className)}
      {...props}
    />
  );
}
