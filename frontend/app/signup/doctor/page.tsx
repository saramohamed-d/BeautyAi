"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ShieldCheck } from "lucide-react";
import { Page } from "@/components/layout/page";
import { Logo } from "@/components/layout/logo";
import { AccountTypeToggle } from "@/components/auth/account-type-toggle";
import { AvatarPicker } from "@/components/doctors/avatar-picker";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import { ApiError } from "@/lib/api-client";

// Mirrors backend/app/schemas/doctor.py (DoctorRegisterRequest).
const schema = z.object({
  full_name: z.string().trim().min(2),
  email: z.string().trim().email(),
  phone: z.string().regex(/^\+?[0-9]{8,15}$/),
  password: z
    .string()
    .min(8)
    .refine((v) => new TextEncoder().encode(v).length <= 72),
  specialty: z.string().trim().min(2),
  sub_specialty: z.string().trim().max(255).optional().or(z.literal("")),
  license_number: z.string().trim().min(3).max(128),
  years_experience: z.coerce.number().int().min(0).max(80).optional().or(z.literal("")),
  medical_degree: z.string().trim().max(255).optional().or(z.literal("")),
  university: z.string().trim().max(255).optional().or(z.literal("")),
  city: z.string().trim().max(128).optional().or(z.literal("")),
  avatar: z.string().optional(),
});
type FormValues = z.input<typeof schema>;

/**
 * "Join as a Doctor" (Sprint 12; docs/verification.md).
 *
 * Signing up creates a real login straight away, but the profile is not
 * public: the next step is the dashboard, where the doctor uploads their
 * licence and ID and submits the application for an admin to review.
 */
export default function DoctorSignupPage() {
  const { t } = useI18n();
  const router = useRouter();
  const { registerDoctor } = useAuth();
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });
  const avatar = watch("avatar");

  async function onSubmit(values: FormValues) {
    setError(null);
    const { years_experience, ...rest } = values;
    const payload = Object.fromEntries(Object.entries(rest).filter(([, value]) => value !== ""));
    try {
      await registerDoctor({
        ...(payload as Omit<FormValues, "years_experience">),
        ...(years_experience === "" || years_experience === undefined
          ? {}
          : { years_experience: Number(years_experience) }),
      } as Parameters<typeof registerDoctor>[0]);
      router.push("/doctor");
    } catch (err) {
      setError(err instanceof ApiError && err.code === "conflict" ? t("signup.exists") : t("errors.generic"));
    }
  }

  return (
    <Page width="narrow" className="pb-12">
      <div className="text-center">
        <Logo className="mx-auto" />
        <h1 className="mt-6 font-display text-[30px] font-semibold leading-tight text-ink">{t("doctorSignup.heading")}</h1>
        <p className="mx-auto mt-1 max-w-sm text-sm leading-relaxed text-ink-muted">{t("doctorSignup.subtitle")}</p>
      </div>
      <AccountTypeToggle current="doctor" />

      <Notice className="mt-4 flex items-start gap-2">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary-dark" aria-hidden="true" />
        <span>{t("doctorSignup.reviewNote")}</span>
      </Notice>

      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <Card className="mt-4 flex flex-col gap-3">
          <Input
            label={t("signup.fullName")}
            placeholder={t("doctorSignup.fullNamePlaceholder")}
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

        <Card className="mt-2.5 flex flex-col gap-3">
          <Input
            label={t("doctorSignup.specialty")}
            placeholder={t("doctorSignup.specialtyPlaceholder")}
            error={errors.specialty && t("validation.required")}
            {...register("specialty")}
          />
          <Input
            label={t("doctorSignup.subSpecialty")}
            placeholder={t("doctorSignup.subSpecialtyPlaceholder")}
            {...register("sub_specialty")}
          />
          <Input
            label={t("doctorSignup.licenseNumber")}
            placeholder={t("doctorSignup.licenseNumberPlaceholder")}
            dir="ltr"
            error={errors.license_number && t("validation.required")}
            {...register("license_number")}
          />
          <Input
            label={t("doctorSignup.yearsExperience")}
            type="number"
            inputMode="numeric"
            min={0}
            max={80}
            {...register("years_experience")}
          />
          <Input
            label={t("doctorSignup.degree")}
            placeholder={t("doctorSignup.degreePlaceholder")}
            {...register("medical_degree")}
          />
          <Input
            label={t("doctorSignup.university")}
            placeholder={t("doctorSignup.universityPlaceholder")}
            {...register("university")}
          />
          <Input label={t("doctorSignup.city")} placeholder={t("doctorSignup.cityPlaceholder")} {...register("city")} />
        </Card>

        <Card className="mt-2.5">
          <AvatarPicker value={avatar} onChange={(key) => setValue("avatar", key)} />
        </Card>

        {error && (
          <p role="alert" className="mt-3 text-sm text-red-700">
            {error}
          </p>
        )}

        <Button type="submit" block className="mt-[15px]" disabled={isSubmitting}>
          {isSubmitting ? t("signup.submitting") : t("doctorSignup.submit")}
        </Button>
      </form>

      <p className="mt-4 text-center text-sm text-ink-muted">
        {t("doctorSignup.patientInstead")}{" "}
        <Link href="/signup" className="font-semibold text-primary-dark hover:underline">
          {t("doctorSignup.patientLink")}
        </Link>
      </p>
      <p className="mt-3 text-center text-sm text-ink-muted">
        {t("signup.haveAccount")}{" "}
        <Link href="/login" className="font-semibold text-primary-dark hover:underline">
          {t("signup.signIn")}
        </Link>
      </p>
    </Page>
  );
}
