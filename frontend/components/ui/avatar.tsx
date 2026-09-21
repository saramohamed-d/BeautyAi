import { cn } from "@/lib/utils";

/** Honorifics dropped before taking initials ("Dr. Nada Ahmed" → "NA", "د. أميرة حسن" → "أح"). */
const PREFIXES = new Set(["dr", "dr.", "د", "د."]);

function initials(name: string): string {
  const words = name.split(/\s+/).filter((w) => w && !PREFIXES.has(w.toLowerCase()));
  return words
    .slice(0, 2)
    .map((w) => w.charAt(0))
    .join("")
    .toUpperCase();
}

const sizes = {
  md: "h-12 w-12 text-base",
  lg: "h-[82px] w-[82px] rounded-[28px] text-2xl",
};

/** Initials in a soft circle — no stock photos or gendered emoji for real providers. */
export function Avatar({ name, size = "md", className }: { name: string; size?: keyof typeof sizes; className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn("grid shrink-0 place-items-center rounded-full bg-primary-soft font-bold text-primary-dark", sizes[size], className)}
    >
      {initials(name)}
    </div>
  );
}
