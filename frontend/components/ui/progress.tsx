/** Thin step progress bar from the demo (`.progress`). `value` is 0–100. */
export function Progress({ value, label }: { value: number; label?: string }) {
  return (
    <div
      className="my-3 h-[5px] rounded-full bg-primary-soft"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value}
      aria-label={label}
    >
      <div className="h-full rounded-full bg-primary-accent transition-[width] duration-300" style={{ width: `${value}%` }} />
    </div>
  );
}
