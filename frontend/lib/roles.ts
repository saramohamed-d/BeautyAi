import {
  BadgeCheck,
  CalendarDays,
  ClipboardList,
  CreditCard,
  Home,
  LayoutDashboard,
  Sparkles,
  Stethoscope,
  UserRound,
  Users,
  type LucideIcon,
} from "lucide-react";
import type { MessageKey } from "@/lib/i18n/types";
import type { Me } from "@/types/auth";

/**
 * Who sees what. Each kind of user gets only the screens they need:
 * patients browse doctors and book; doctors, clinic admins and platform
 * admins each work from their own dashboard and never see the patient
 * side (other doctors, booking, the AI chat).
 */
export type Audience = "guest" | "patient" | "doctor" | "clinic_admin" | "platform_admin";

export interface NavItem {
  href: string;
  label: MessageKey;
  icon: LucideIcon;
  /** Path prefixes that mark this item as the current page. */
  match: string[];
}

export function audienceOf(me: Pick<Me, "user" | "clinics"> | null): Audience {
  if (!me) return "guest";
  if (me.user.role === "platform_admin") return "platform_admin";
  if (me.user.role === "doctor") return "doctor";
  if (me.user.role === "clinic_admin" || (me.clinics ?? []).length > 0) return "clinic_admin";
  return "patient";
}

/** Where each kind of user lands after logging in (and when they open a page meant for someone else). */
export const HOME: Record<Audience, string> = {
  guest: "/",
  patient: "/",
  doctor: "/doctor",
  clinic_admin: "/clinic",
  platform_admin: "/admin",
};

const PATIENT_NAV: NavItem[] = [
  { href: "/", label: "nav.home", icon: Home, match: ["/"] },
  { href: "/doctors", label: "nav.doctors", icon: Stethoscope, match: ["/doctors", "/clinics", "/booking"] },
  { href: "/consultation", label: "nav.aiConsultation", icon: Sparkles, match: ["/consultation", "/assistant"] },
  { href: "/appointments", label: "nav.appointments", icon: CalendarDays, match: ["/appointments"] },
  { href: "/account", label: "nav.profile", icon: UserRound, match: ["/account"] },
];

export const NAV: Record<Audience, NavItem[]> = {
  guest: PATIENT_NAV,
  patient: PATIENT_NAV,
  doctor: [
    { href: "/doctor", label: "nav.dashboard", icon: LayoutDashboard, match: ["/doctor"] },
    { href: "/account", label: "nav.profile", icon: UserRound, match: ["/account"] },
  ],
  clinic_admin: [
    { href: "/clinic", label: "nav.dashboard", icon: LayoutDashboard, match: ["/clinic"] },
    { href: "/clinic/appointments", label: "nav.appointments", icon: CalendarDays, match: ["/clinic/appointments"] },
    { href: "/clinic/team", label: "nav.team", icon: Users, match: ["/clinic/team"] },
    { href: "/account", label: "nav.profile", icon: UserRound, match: ["/account"] },
  ],
  platform_admin: [
    { href: "/admin", label: "nav.dashboard", icon: LayoutDashboard, match: ["/admin"] },
    { href: "/admin/verification", label: "nav.verification", icon: BadgeCheck, match: ["/admin/verification"] },
    { href: "/admin/payments", label: "nav.payments", icon: CreditCard, match: ["/admin/payments"] },
    { href: "/admin/users", label: "nav.users", icon: ClipboardList, match: ["/admin/users", "/admin/audit", "/admin/messages"] },
    { href: "/account", label: "nav.profile", icon: UserRound, match: ["/account"] },
  ],
};

/** The current page for a nav item; "/" and dashboard roots only match exactly or their own sub-pages. */
export function isActive(pathname: string, item: NavItem, items: NavItem[]): boolean {
  const hit = (m: string) => (m === "/" ? pathname === "/" : pathname === m || pathname.startsWith(`${m}/`));
  if (!item.match.some(hit)) return false;
  // A more specific item (e.g. /clinic/team) wins over its dashboard root (/clinic).
  return !items.some((other) => other !== item && other.match.some((m) => m.length > item.href.length && hit(m)));
}

/** Patient-side screens. Staff who open one are sent to their own dashboard. */
const PATIENT_AREAS = ["/", "/doctors", "/clinics", "/procedures", "/learn", "/booking", "/consultation", "/assistant", "/appointments", "/payment"];

export function isPatientArea(pathname: string): boolean {
  return PATIENT_AREAS.some((area) => (area === "/" ? pathname === "/" : pathname === area || pathname.startsWith(`${area}/`)));
}
