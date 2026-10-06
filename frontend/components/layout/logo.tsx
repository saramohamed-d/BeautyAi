import Link from "next/link";
import { cn } from "@/lib/utils";

/** The lotus mark on its own (also used as the chat assistant's icon). */
export function LotusMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" aria-hidden="true" className={cn("h-7 w-7", className)}>
      {/* Side petals, then the centre petal on top, then the waterline. */}
      <path d="M15.6 25.5C9.5 25 5.2 21 4.5 13.8c5.2.4 9.3 3.5 11.1 8.6" fill="#F6B8CB" stroke="#D6336C" strokeWidth="1.3" strokeLinejoin="round" />
      <path d="M16.4 25.5c6.1-.5 10.4-4.5 11.1-11.7-5.2.4-9.3 3.5-11.1 8.6" fill="#F6B8CB" stroke="#D6336C" strokeWidth="1.3" strokeLinejoin="round" />
      <path d="M16 4.5c3.6 3.4 5.4 7.3 5.4 11.4S19.6 22.9 16 25.5c-3.6-2.6-5.4-5.5-5.4-9.6S12.4 7.9 16 4.5Z" fill="#F06A95" stroke="#D6336C" strokeWidth="1.3" strokeLinejoin="round" />
      <path d="M9 27.5h14" stroke="#D6336C" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}

/**
 * "Beauty AI" wordmark with the lotus. The text is always Latin and LTR,
 * but the link itself follows the page direction so it sits at the start
 * edge in RTL.
 */
export function Logo({ className, href = "/" }: { className?: string; href?: string }) {
  return (
    <Link href={href} className={cn("inline-flex items-center gap-1.5 text-[22px] font-semibold text-ink", className)}>
      <LotusMark />
      <span dir="ltr" className="font-display tracking-tight">
        Beauty <span className="text-primary">AI</span>
      </span>
    </Link>
  );
}
