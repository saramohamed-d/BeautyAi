"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { UserPlus } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { usePatientContext } from "@/lib/patient-context";
import { createPatient } from "@/services/patient-service";
import { ApiError } from "@/lib/api-client";

const schema = z.object({
  full_name: z.string().min(2, "الاسم لازم يكون حرفين على الأقل"),
  phone: z.string().regex(/^\+?[0-9]{8,15}$/, "رقم الهاتف غير صحيح"),
  email: z.union([z.string().email("بريد إلكتروني غير صحيح"), z.literal("")]).optional(),
});
type FormValues = z.infer<typeof schema>;

/**
 * UI-ONLY signup. Creates a real Patient row via Sprint 2's POST
 * /patients (so the account genuinely exists in the database), but
 * there is still no password and no backend session — see the same
 * note in app/login/page.tsx.
 */
export default function SignupPage() {
  const router = useRouter();
  const { setPatient } = usePatientContext();
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
    try {
      const patient = await createPatient({
        full_name: values.full_name,
        phone: values.phone,
        email: values.email || undefined,
      });
      setPatient(patient);
      router.push("/account");
    } catch (err) {
      if (err instanceof ApiError && err.code === "conflict") {
        setError("يوجد حساب بهذا الرقم بالفعل. جرّبي تسجيل الدخول بدلاً من ذلك.");
      } else {
        setError(err instanceof ApiError ? err.message : "حدث خطأ. حاولي مرة أخرى.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-4 py-12 md:px-6">
      <div className="rounded-3xl border border-border bg-surface p-8">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <UserPlus className="h-8 w-8 text-primary" strokeWidth={1.5} />
          <h1 className="text-2xl font-bold text-ink">إنشاء حساب</h1>
          <p className="text-sm text-ink-muted">أنشئي حسابك لحفظ مواعيدك ومتابعتها بسهولة.</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <Input label="الاسم بالكامل" placeholder="اسمك بالكامل" error={errors.full_name?.message} {...register("full_name")} />
          <Input label="رقم الهاتف" placeholder="01xxxxxxxxx" dir="ltr" error={errors.phone?.message} {...register("phone")} />
          <Input label="البريد الإلكتروني (اختياري)" placeholder="example@mail.com" dir="ltr" error={errors.email?.message} {...register("email")} />

          {error && <p className="text-sm text-red-600">{error}</p>}

          <Button type="submit" size="lg" disabled={isSubmitting}>
            {isSubmitting ? "جاري الإنشاء..." : "إنشاء حساب"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-ink-muted">
          لديك حساب بالفعل؟ <Link href="/login" className="font-medium text-primary">تسجيل الدخول</Link>
        </p>
      </div>
    </div>
  );
}
