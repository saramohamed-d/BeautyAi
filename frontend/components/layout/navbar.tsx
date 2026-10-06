"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { UserRound } from "lucide-react";
import { Logo } from "@/components/layout/logo";
import { LanguageToggle } from "@/components/layout/language-toggle";
import { LinkButton } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import { HOME, NAV, isActive } from "@/lib/roles";
import { cn } from "@/lib/utils";

/**
 * Desktop-only top bar; phones use the bottom tab bar (bottom-nav.tsx).
 * The links depend on who is logged in (lib/roles.ts): patients and
 * visitors see the patient app, staff only their own dashboard.
 */
export function Navbar() {
  const { t } = useI18n();
  const { user, patient, doctor, audience } = useAuth();
  const pathname = usePathname();
  // Profile sits on the right as the account button, so it's not repeated in the middle.
  const items = NAV[audience].filter((item) => item.href !== "/account");
  const name = patient?.full_name ?? doctor?.full_name;

  return (
    <header className="sticky top-0 z-40 hidden border-b border-border bg-white/85 backdrop-blur md:block">
      <div className="mx-auto flex h-[68px] max-w-6xl items-center justify-between gap-6 px-6">
        <Logo href={HOME[audience]} />
        <nav aria-label={t("nav.mainNav")} className="flex items-center gap-7">
          {items.map((item) => {
            const active = isActive(pathname, item, items);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative py-1 text-sm font-medium transition-colors hover:text-primary-dark",
                  active ? "text-primary-dark after:absolute after:inset-x-0 after:-bottom-0.5 after:h-0.5 after:rounded-full after:bg-primary" : "text-ink"
                )}
              >
                {t(item.label)}
              </Link>
            );
          })}
          {audience === "guest" && (
            <Link href="/#how-it-works" className="py-1 text-sm font-medium text-ink hover:text-primary-dark">
              {t("nav.howItWorks")}
            </Link>
          )}
        </nav>
        <div className="flex items-center gap-2.5">
          <LanguageToggle />
          {user ? (
            <Link
              href="/account"
              className="inline-flex h-10 items-center gap-2 rounded-full border border-border bg-surface ps-1 pe-4 text-sm font-semibold text-ink hover:border-primary-line"
            >
              <span className="grid h-8 w-8 place-items-center rounded-full bg-primary-soft text-primary-dark">
                <UserRound className="h-4 w-4" strokeWidth={1.75} />
              </span>
              {name?.split(" ").slice(0, 2).join(" ") ?? t(`roles.${user.role}`)}
            </Link>
          ) : (
            <>
              <LinkButton href="/login" size="sm" variant="secondary" className="rounded-full px-5">
                {t("nav.signIn")}
              </LinkButton>
              <LinkButton href="/signup" size="sm" className="rounded-full px-5">
                {t("nav.getStarted")}
              </LinkButton>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
