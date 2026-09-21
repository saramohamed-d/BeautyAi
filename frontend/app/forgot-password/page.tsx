"use client";

import { useState } from "react";
import Link from "next/link";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { useI18n } from "@/lib/i18n/provider";
import { forgotPassword } from "@/services/auth-service";

/**
 * "I forgot my password" (Sprint 17).
 *
 * The answer is the same whether or not the account exists — the page
 * can't be used to find out who has one — so the confirmation is shown
 * on any successful request.
 */
export default function ForgotPasswordPage() {
  const { t } = useI18n();
  const [identifier, setIdentifier] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await forgotPassword(identifier.trim());
      setSent(true);
    } catch {
      setError(t("errors.generic"));
    }
    setBusy(false);
  }

  return (
    <Page width="narrow" className="pb-12">
      <PageHeader title={t("forgotPassword.title")} backHref="/login" />
      <h2 className="text-[25px] font-bold leading-tight text-ink">{t("forgotPassword.heading")}</h2>
      <p className="mt-1 text-sm leading-relaxed text-ink-muted">{t("forgotPassword.subtitle")}</p>

      {sent ? (
        <Notice className="mt-4">{t("forgotPassword.sent")}</Notice>
      ) : (
        <form onSubmit={submit} noValidate>
          <Card className="mt-4">
            <Input
              label={t("login.identifier")}
              placeholder={t("login.identifierPlaceholder")}
              dir="ltr"
              autoComplete="username"
              value={identifier}
              onChange={(event) => setIdentifier(event.target.value)}
            />
          </Card>
          {error && (
            <p role="alert" className="mt-3 text-sm text-red-700">
              {error}
            </p>
          )}
          <Button type="submit" block className="mt-[15px]" disabled={busy || identifier.trim().length < 3}>
            {busy ? t("forgotPassword.sending") : t("forgotPassword.submit")}
          </Button>
        </form>
      )}

      <p className="mt-5 text-center text-sm text-ink-muted">
        <Link href="/login" className="font-semibold text-primary-dark hover:underline">
          {t("forgotPassword.backToLogin")}
        </Link>
      </p>
    </Page>
  );
}
