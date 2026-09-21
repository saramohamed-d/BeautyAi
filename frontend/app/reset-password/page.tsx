"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/lib/i18n/provider";
import { ApiError } from "@/lib/api-client";
import { resetPassword } from "@/services/auth-service";

/** Setting a new password from the emailed link (Sprint 17). */
function ResetPassword() {
  const { t } = useI18n();
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await resetPassword(token, password);
      setDone(true);
      setTimeout(() => router.push("/login"), 2500);
    } catch (err) {
      setError(
        err instanceof ApiError && err.code === "invalid_token"
          ? t("resetPassword.badLink")
          : err instanceof ApiError && err.status === 422
            ? t("validation.password")
            : t("errors.generic")
      );
    }
    setBusy(false);
  }

  if (!token) {
    return (
      <Page width="narrow">
        <PageHeader title={t("resetPassword.title")} backHref="/login" />
        <Card className="mt-8 text-center">
          <p className="font-bold text-ink">{t("resetPassword.badLink")}</p>
          <Link href="/forgot-password" className="mt-3 inline-block font-semibold text-primary-dark hover:underline">
            {t("resetPassword.askAgain")}
          </Link>
        </Card>
      </Page>
    );
  }

  return (
    <Page width="narrow" className="pb-12">
      <PageHeader title={t("resetPassword.title")} backHref="/login" />
      <h2 className="text-[25px] font-bold leading-tight text-ink">{t("resetPassword.heading")}</h2>
      <p className="mt-1 text-sm leading-relaxed text-ink-muted">{t("resetPassword.subtitle")}</p>

      {done ? (
        <Notice className="mt-4">{t("resetPassword.done")}</Notice>
      ) : (
        <form onSubmit={submit} noValidate>
          <Card className="mt-4">
            <Input
              label={t("signup.password")}
              type="password"
              dir="ltr"
              autoComplete="new-password"
              placeholder={t("signup.passwordPlaceholder")}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </Card>
          {error && (
            <p role="alert" className="mt-3 text-sm text-red-700">
              {error}
            </p>
          )}
          <Button type="submit" block className="mt-[15px]" disabled={busy || password.length < 8}>
            {busy ? t("resetPassword.saving") : t("resetPassword.submit")}
          </Button>
        </form>
      )}
    </Page>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<Page width="narrow"><Skeleton className="mt-8 h-64" /></Page>}>
      <ResetPassword />
    </Suspense>
  );
}
