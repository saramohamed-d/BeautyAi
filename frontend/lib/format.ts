/**
 * Formatting + lightweight date-grid helpers.
 *
 * Design decision: no date library (date-fns, dayjs) added — the booking
 * calendar only needs "days in a month" and "is this the same day"
 * arithmetic, which native Date covers in ~20 lines. Pulling in a date
 * library for that would be an unnecessary dependency per the project's
 * own rule of thumb.
 */

const ARABIC_MONTHS = [
  "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
  "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
];
const ARABIC_WEEKDAYS_SHORT = ["أحد", "اثنين", "ثلاثاء", "أربعاء", "خميس", "جمعة", "سبت"];

export function formatDateArabic(date: Date): string {
  return `${date.getDate()} ${ARABIC_MONTHS[date.getMonth()]} ${date.getFullYear()}`;
}

export function formatTime(date: Date): string {
  return date.toLocaleTimeString("ar-EG", { hour: "2-digit", minute: "2-digit" });
}

export function formatCurrency(amount: number | string | null | undefined, currency = "EGP"): string {
  if (amount === null || amount === undefined) return "—";
  const value = typeof amount === "string" ? parseFloat(amount) : amount;
  if (Number.isNaN(value)) return "—";
  return `${value.toLocaleString("ar-EG")} ${currency === "EGP" ? "ج.م" : currency}`;
}

export function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

export function startOfDay(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

export function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

/** Returns the next `count` calendar days starting today, for a simple horizontal date strip. */
export function nextDays(count: number, from: Date = new Date()): Date[] {
  const start = startOfDay(from);
  return Array.from({ length: count }, (_, i) => addDays(start, i));
}

export function weekdayShortArabic(date: Date): string {
  return ARABIC_WEEKDAYS_SHORT[date.getDay()] ?? "";
}
