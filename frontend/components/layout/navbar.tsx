"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { UserRound } from "lucide-react";
import { Logo } from "@/components/layout/logo";
import { LanguageToggle } from "@/components/layout/language-toggle";
import { LinkButton } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/types";
import { cn } from "@/lib/utils";

const LINKS: { href: string; label: MessageKey }[] = [
  { href: "/doctors", label: "nav.doctors" },
  { href: "/clinics", label: "nav.clinics" },
  { href: "/procedures", label: "nav.procedures" },
  { href: "/learn", label: "nav.learn" },
  { href: "/consultation", label: "nav.aiConsultation" },
];

/** Desktop-only top bar. Phones use the bottom tab bar instead (see bottom-nav.tsx). */
export function Navbar() {
  const { t } = useI18n();
  const { user, patient } = useAuth();
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 hidden border-b border-border bg-bg/90 backdrop-blur md:block">
      <div className="mx-auto flex h-16 max-w-5xl items-center justify-between gap-6 px-[18px]">
        <Logo className="text-2xl" />
        <nav aria-label={t("nav.mainNav")} className="flex items-center gap-6">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "text-sm font-medium hover:text-ink",
                pathname.startsWith(link.href) ? "font-bold text-primary-dark" : "text-ink-muted"
              )}
            >
              {t(link.label)}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <LanguageToggle />
          {user ? (
            <Link
              href="/account"
              className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-border bg-surface px-3 text-sm font-semibold text-ink hover:border-primary-line"
            >
              <UserRound className="h-4 w-4" strokeWidth={1.75} />
              {patient?.full_name.split(" ")[0] ?? t(`roles.${user.role}`)}
            </Link>
          ) : (
            <Link href="/login" className="px-2 text-sm font-semibold text-ink-muted hover:text-ink">
              {t("nav.signIn")}
            </Link>
          )}
          <LinkButton href="/booking" size="sm">
            {t("nav.bookNow")}
          </LinkButton>
        </div>
      </div>
    </header>
  );
}
