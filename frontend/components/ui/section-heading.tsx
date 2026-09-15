export function SectionHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      {eyebrow && <p className="text-sm font-medium text-primary">{eyebrow}</p>}
      <h2 className="text-2xl font-semibold text-ink md:text-3xl">{title}</h2>
      {description && <p className="max-w-2xl text-ink-muted">{description}</p>}
    </div>
  );
}
