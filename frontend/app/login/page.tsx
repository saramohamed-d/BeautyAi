"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { LogIn } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { usePatientContext } from "@/lib/patient-context";
import { searchPatientsByPhone } from "@/services/patient-service";
import { ApiError } from "@/lib/api-client";

const schema = z.object({
  phone: z.string().regex(/^\+?[0-9]{8,15}$/, "رقم الهاتف غير صحيح"),
});
type FormValues = z.infer<typeof schema>;

/**
 * UI-ONLY login. There is no password, no session, no JWT — Sprint 3
 * excludes backend authentication entirely per the brief. This form
 * looks up a real Patient row by phone through Sprint 2's API and, if
 * found, sets it as the in-memory "current patient" (see
 * lib/patient-context.tsx). This is a placeholder identity mechanism,
 * not a security boundary — it should not be mistaken for real auth by
 * anyone reading this code.
 */
export default function LoginPage() {
  const router = useRouter();
  const { setPatient } = usePatientContext();
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    setIsSubmitting(true);
    setError(null);
    setNotFound(false);
    try {
      const results = await searchPatientsByPhone(values.phone);
      const match = results.items.find((p) => p.phone === values.phone);
      if (!match) {
        setNotFound(true);
        return;
      }
      setPatient(match);
      router.push("/account");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "حدث خطأ. حاولي مرة أخرى.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-4 py-12 md:px-6">
      <div className="rounded-3xl border border-border bg-surface p-8">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <LogIn className="h-8 w-8 text-primary" strokeWidth={1.5} />
          <h1 className="text-2xl font-bold text-ink">تسجيل الدخول</h1>
          <p className="text-sm text-ink-muted">أدخلي رقم هاتفك لعرض حسابك ومواعيدك.</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <Input label="رقم الهاتف" placeholder="01xxxxxxxxx" dir="ltr" error={errors.phone?.message} {...register("phone")} />

          {notFound && (
            <p className="text-sm text-ink-muted">
              لا يوجد حساب بهذا الرقم.{" "}
              <Link href="/signup" className="font-medium text-primary">أنشئي حساباً جديداً</Link>
            </p>
          )}
          {error && <p className="text-sm text-red-600">{error}</p>}

          <Button type="submit" size="lg" disabled={isSubmitting}>
            {isSubmitting ? "جاري البحث..." : "دخول"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-ink-muted">
          ليس لديك حساب؟ <Link href="/signup" className="font-medium text-primary">أنشئي حساباً</Link>
        </p>
      </div>
    </div>
  );
}
