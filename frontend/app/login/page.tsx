"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Page } from "@/components/layout/page";
import { Logo } from "@/components/layout/logo";
import { LanguageToggle } from "@/components/layout/language-toggle";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button, LinkButton } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import { safeNext, withNext } from "@/lib/safe-next";
import { HOME, audienceOf, isPatientArea } from "@/lib/roles";
import { ApiError } from "@/lib/api-client";

const schema = z.object({
  identifier: z.string().trim().min(3),
  password: z.string().min(1),
});
type FormValues = z.infer<typeof schema>;

function LoginContent() {
  const { t } = useI18n();
  const router = useRouter();
  const next = useSearchParams().get("next");
  const { login } = useAuth();
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    setError(null);
    try {
      const me = await login(values.identifier, values.password);
      // Everyone lands on their own home (lib/roles.ts); staff never land on the patient side.
      const audience = audienceOf(me);
      const target = next ? safeNext(next) : HOME[audience];
      const staff = audience !== "patient";
      router.push(staff && isPatientArea(target) ? HOME[audience] : target);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setError(t("login.invalid"));
      else if (err instanceof ApiError && err.status === 403) setError(t("login.blocked"));
      else setError(t("errors.generic"));
    }
  }

  return (
    <Page width="narrow" className="pb-12">
      <div className="flex justify-end">
        <LanguageToggle />
      </div>

      <div className="pt-8 text-center md:pt-4">
        <Logo className="mx-auto" />
        <h1 className="mt-8 font-display text-[32px] font-semibold leading-tight text-ink">{t("login.welcomeBack")}</h1>
        <p className="mx-auto mt-2 max-w-xs text-sm leading-relaxed text-ink-muted">{t("login.subtitle")}</p>
      </div>

      <Card className="mt-6">
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-3" noValidate>
          <Input
            label={t("login.identifier")}
            placeholder={t("login.identifierPlaceholder")}
            dir="ltr"
            autoComplete="username"
            error={errors.identifier && t("validation.required")}
            {...register("identifier")}
          />
          <Input
            label={t("login.password")}
            type="password"
            placeholder="••••••••"
            dir="ltr"
            autoComplete="current-password"
            error={errors.password && t("validation.required")}
            {...register("password")}
          />

          {error && (
            <p role="alert" className="text-sm text-red-700">
              {error}
            </p>
          )}

          <Button type="submit" block className="mt-2" disabled={isSubmitting}>
            {isSubmitting ? t("login.submitting") : t("login.submit")}
          </Button>
          <LinkButton href={withNext("/signup", next)} variant="secondary" block>
            {t("login.createAccount")}
          </LinkButton>
          <Link href="/forgot-password" className="text-center text-sm font-semibold text-primary-dark hover:underline">
            {t("login.forgotPassword")}
          </Link>
        </form>
      </Card>
      <p className="mt-5 text-center text-sm text-ink-muted">
        {t("doctorSignup.doctorPrompt")}{" "}
        <Link href="/signup/doctor" className="font-semibold text-primary-dark hover:underline">
          {t("doctorSignup.doctorLink")}
        </Link>
      </p>
    </Page>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<Page width="narrow"><Skeleton className="h-96" /></Page>}>
      <LoginContent />
    </Suspense>
  );
}
