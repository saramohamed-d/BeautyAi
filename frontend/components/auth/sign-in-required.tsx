"use client";

import { LogIn } from "lucide-react";
import { Card } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import { withNext } from "@/lib/safe-next";

/**
 * Shown where booking needs a patient account. Login/signup return to
 * `next`, and the booking draft survives the round trip because it lives
 * in BookingContext, not in the page.
 */
export function SignInRequired({ next }: { next: string }) {
  const { t } = useI18n();
  const { user } = useAuth();

  return (
    <Card className="text-center">
      <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-full bg-primary-soft text-primary-dark">
        <LogIn className="h-5 w-5" strokeWidth={1.75} />
      </div>
      <p className="font-bold text-ink">{t("booking.signInTitle")}</p>
      <p className="mt-1 text-sm text-ink-muted">{user ? t("booking.patientOnly") : t("booking.signInBody")}</p>
      {!user && (
        <div className="mt-4 flex flex-col gap-[9px]">
          <LinkButton href={withNext("/login", next)} block>
            {t("login.submit")}
          </LinkButton>
          <LinkButton href={withNext("/signup", next)} variant="secondary" block>
            {t("login.createAccount")}
          </LinkButton>
        </div>
      )}
    </Card>
  );
}
