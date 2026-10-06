"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import { NAV, isActive } from "@/lib/roles";
import { cn } from "@/lib/utils";

/** Screens that are full-screen on phones, without the tab bar. */
const HIDDEN_ON = ["/login", "/signup"];

/** Also covers nested routes such as /signup/doctor. */
function isHidden(pathname: string): boolean {
  return HIDDEN_ON.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

/** Phone-only tab bar, with the same per-role items as the desktop top bar. */
export function BottomNav() {
  const { t } = useI18n();
  const { audience } = useAuth();
  const pathname = usePathname();
  if (isHidden(pathname)) return null;
  const items = NAV[audience];

  return (
    <nav
      aria-label={t("nav.mainNav")}
      className="fixed inset-x-0 bottom-0 z-40 mx-auto grid h-[76px] max-w-[430px] border-t border-border bg-white px-2 pb-[env(safe-area-inset-bottom)] md:hidden"
      style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}
    >
      {items.map((item) => {
        const active = isActive(pathname, item, items);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex flex-col items-center justify-center gap-1 text-center text-[10.5px] leading-tight",
              active ? "font-bold text-primary-dark" : "text-ink-muted"
            )}
          >
            <span className={cn("grid h-8 w-12 place-items-center rounded-full", active && "bg-primary-soft")}>
              <Icon className="h-5 w-5" strokeWidth={active ? 2.25 : 1.75} />
            </span>
            {t(item.label)}
          </Link>
        );
      })}
    </nav>
  );
}
