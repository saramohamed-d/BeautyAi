"use client";

import Link from "next/link";
import { Stethoscope, UserRound } from "lucide-react";
import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

/** "I'm a Patient / I'm a Doctor" switch at the top of the two sign-up forms. */
export function AccountTypeToggle({ current }: { current: "patient" | "doctor" }) {
  const { t } = useI18n();
  const options = [
    { key: "patient", href: "/signup", label: t("signup.asPatient"), icon: UserRound },
    { key: "doctor", href: "/signup/doctor", label: t("signup.asDoctor"), icon: Stethoscope },
  ] as const;

  return (
    <div className="mt-5 grid grid-cols-2 gap-2" role="group" aria-label={t("signup.accountType")}>
      {options.map(({ key, href, label, icon: Icon }) => {
        const active = key === current;
        return (
          <Link
            key={key}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex h-11 items-center justify-center gap-2 rounded-xl border text-sm font-semibold transition-colors",
              active ? "border-primary bg-primary-soft text-primary-dark" : "border-border bg-surface text-ink hover:border-primary-line"
            )}
          >
            <Icon className="h-4 w-4" aria-hidden="true" /> {label}
          </Link>
        );
      })}
    </div>
  );
}
