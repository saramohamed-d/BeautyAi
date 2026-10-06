"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Page } from "@/components/layout/page";
import { Logo } from "@/components/layout/logo";
import { AccountTypeToggle } from "@/components/auth/account-type-toggle";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import { safeNext, withNext } from "@/lib/safe-next";
import { ApiError } from "@/lib/api-client";

// Mirrors backend/app/schemas/auth.py: 8+ characters, at most 72 bytes (bcrypt's limit).
const schema = z.object({
  full_name: z.string().trim().min(2),
  email: z.string().trim().email(),
  phone: z.string().regex(/^\+?[0-9]{8,15}$/),
  password: z
    .string()
    .min(8)
    .refine((v) => new TextEncoder().encode(v).length <= 72),
});
type FormValues = z.infer<typeof schema>;

function SignupContent() {
  const { t, locale } = useI18n();
  const router = useRouter();
  const next = useSearchParams().get("next");
  const { register: signUp } = useAuth();
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    setError(null);
    try {
      await signUp({ ...values, preferred_language: locale });
      router.push(safeNext(next));
    } catch (err) {
      setError(err instanceof ApiError && err.code === "conflict" ? t("signup.exists") : t("errors.generic"));
    }
  }

  return (
    <Page width="narrow" className="pb-12">
      <div className="text-center">
        <Logo className="mx-auto" />
        <h1 className="mt-6 font-display text-[30px] font-semibold leading-tight text-ink">{t("signup.heading")}</h1>
        <p className="mx-auto mt-1 max-w-sm text-sm leading-relaxed text-ink-muted">{t("signup.subtitle")}</p>
      </div>
      <AccountTypeToggle current="patient" />

      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <Card className="mt-4 flex flex-col gap-3">
          <Input
            label={t("signup.fullName")}
            placeholder={t("signup.fullNamePlaceholder")}
            autoComplete="name"
            error={errors.full_name && t("validation.name")}
            {...register("full_name")}
          />
          <Input
            label={t("signup.email")}
            placeholder={t("signup.emailPlaceholder")}
            dir="ltr"
            type="email"
            autoComplete="email"
            error={errors.email && t("validation.email")}
            {...register("email")}
          />
          <Input
            label={t("signup.phone")}
            placeholder={t("login.phonePlaceholder")}
            dir="ltr"
            inputMode="tel"
            autoComplete="tel"
            error={errors.phone && t("validation.phone")}
            {...register("phone")}
          />
          <Input
            label={t("signup.password")}
            type="password"
            placeholder={t("signup.passwordPlaceholder")}
            dir="ltr"
            autoComplete="new-password"
            error={errors.password && t("validation.password")}
            {...register("password")}
          />
        </Card>

        {error && (
          <p role="alert" className="mt-3 text-sm text-red-700">
            {error}
          </p>
        )}

        <Button type="submit" block className="mt-[15px]" disabled={isSubmitting}>
          {isSubmitting ? t("signup.submitting") : t("signup.submit")}
        </Button>
      </form>

      <p className="mt-4 text-center text-sm text-ink-muted">
        {t("signup.haveAccount")}{" "}
        <Link href={withNext("/login", next)} className="font-semibold text-primary-dark hover:underline">
          {t("signup.signIn")}
        </Link>
      </p>
    </Page>
  );
}

export default function SignupPage() {
  return (
    <Suspense fallback={<Page width="narrow"><Skeleton className="h-96" /></Page>}>
      <SignupContent />
    </Suspense>
  );
}
