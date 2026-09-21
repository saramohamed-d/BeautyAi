import Link from "next/link";
import { cn } from "@/lib/utils";

/**
 * "beautyAI" wordmark. The text is always Latin and LTR, but the link
 * itself follows the page direction so it sits at the start edge in RTL.
 */
export function Logo({ className }: { className?: string }) {
  return (
    <Link href="/" className={cn("self-start text-[27px] font-bold tracking-[-1px] text-ink", className)}>
      <span dir="ltr">
        beauty<span className="text-primary-accent">AI</span>
      </span>
    </Link>
  );
}
