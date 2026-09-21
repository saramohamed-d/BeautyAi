/**
 * Date-grid helpers for the booking calendar.
 *
 * Locale-aware display formatting (dates, times, currency) lives in the
 * i18n provider (`useI18n().formatDate` etc.) so it follows the selected
 * language. No date library: native Date covers the arithmetic below.
 */

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

/** Returns the next `count` calendar days starting today, for a horizontal date strip. */
export function nextDays(count: number, from: Date = new Date()): Date[] {
  const start = startOfDay(from);
  return Array.from({ length: count }, (_, i) => addDays(start, i));
}
