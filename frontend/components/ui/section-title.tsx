import Link from "next/link";

/** Row with a section title and an optional "View all"-style link (the demo's `.section`). */
export function SectionTitle({ title, href, linkLabel }: { title: string; href?: string; linkLabel?: string }) {
  return (
    <div className="mb-2 mt-6 flex items-center justify-between">
      <h2 className="text-sm font-bold text-ink md:text-base">{title}</h2>
      {href && linkLabel && (
        <Link href={href} className="text-xs font-semibold text-primary-dark hover:underline">
          {linkLabel}
        </Link>
      )}
    </div>
  );
}
