"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CalendarDays, Home, Sparkles, UserRound, type LucideIcon } from "lucide-react";
import { useI18n } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/types";
import { cn } from "@/lib/utils";

const TABS: { href: string; label: MessageKey; icon: LucideIcon; match: string[] }[] = [
  { href: "/", label: "nav.home", icon: Home, match: ["/"] },
  { href: "/appointments", label: "nav.appointments", icon: CalendarDays, match: ["/appointments"] },
  { href: "/consultation", label: "nav.consult", icon: Sparkles, match: ["/consultation", "/assistant"] },
  { href: "/account", label: "nav.profile", icon: UserRound, match: ["/account"] },
];

/** Screens that are full-screen on phones, without the tab bar (as in the demo). */
const HIDDEN_ON = ["/login", "/signup"];

/** Also covers nested routes such as /signup/doctor. */
function isHidden(pathname: string): boolean {
  return HIDDEN_ON.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

function isActive(pathname: string, match: string[]): boolean {
  return match.some((m) => (m === "/" ? pathname === "/" : pathname.startsWith(m)));
}

/** Phone-only tab bar (the demo's `.bottom`). */
export function BottomNav() {
  const { t } = useI18n();
  const pathname = usePathname();
  if (isHidden(pathname)) return null;

  return (
    <nav
      aria-label={t("nav.mainNav")}
      className="fixed inset-x-0 bottom-0 z-40 mx-auto grid h-[76px] max-w-[430px] grid-cols-4 border-t border-border bg-[#fffdfd] px-2 pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      {TABS.map(({ href, label, icon: Icon, match }) => {
        const active = isActive(pathname, match);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex flex-col items-center justify-center gap-1 text-[11px]",
              active ? "font-bold text-primary-dark" : "text-ink-muted"
            )}
          >
            <Icon className="h-5 w-5" strokeWidth={active ? 2.25 : 1.75} />
            {t(label)}
          </Link>
        );
      })}
    </nav>
  );
}
