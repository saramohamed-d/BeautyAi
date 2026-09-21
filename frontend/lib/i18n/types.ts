import type { en } from "@/lib/i18n/messages/en";

/** Same shape as the English dictionary, with every leaf widened to string. */
type Widen<T> = { [K in keyof T]: T[K] extends string ? string : Widen<T[K]> };
export type Messages = Widen<typeof en>;

/** Dot-path of every translatable string, e.g. "home.greeting.morning". */
type Leaves<T, P extends string = ""> = {
  [K in keyof T & string]: T[K] extends string ? `${P}${K}` : Leaves<T[K], `${P}${K}.`>;
}[keyof T & string];
export type MessageKey = Leaves<Messages>;

/** Top-level sections that map raw backend values to labels (see `label()`). */
export type ValueSection =
  | "specialties"
  | "categories"
  | "appointmentStatus"
  | "paymentStatus"
  | "paymentMethod"
  | "notificationStatus"
  | "notificationTemplate"
  | "concerns";
