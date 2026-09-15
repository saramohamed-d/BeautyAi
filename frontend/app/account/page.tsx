"use client";

import Link from "next/link";
import { User, Calendar, LogIn, Phone, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePatientContext } from "@/lib/patient-context";

/**
 * Patient profile overview. Since Sprint 3 has no backend auth, "signed
 * in" here means PatientContext holds a real Patient row (set via
 * /login, /signup, or the booking flow) — see lib/patient-context.tsx
 * for the documented limitation (in-memory only, cleared on reload).
 */
export default function AccountPage() {
  const { patient } = usePatientContext();

  if (!patient) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center md:px-6">
        <User className="mx-auto h-10 w-10 text-ink-muted" strokeWidth={1.5} />
        <h1 className="mt-4 text-xl font-semibold text-ink">لم تسجّلي الدخول بعد</h1>
        <p className="mt-2 text-ink-muted">
          سجّلي الدخول أو أنشئي حساباً لعرض بياناتك ومواعيدك. يمكنك أيضاً حجز موعد مباشرة وسيتم إنشاء حسابك تلقائياً.
        </p>
        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Link href="/login"><Button><LogIn className="h-4 w-4" /> تسجيل الدخول</Button></Link>
          <Link href="/booking"><Button variant="outline">احجزي موعداً</Button></Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-12 md:px-6">
      <div className="rounded-3xl border border-border bg-surface p-8">
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary-soft text-primary-dark">
            <User className="h-7 w-7" strokeWidth={1.5} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-ink">{patient.full_name}</h1>
            <p className="flex items-center gap-1.5 text-sm text-ink-muted"><Phone className="h-3.5 w-3.5" /> {patient.phone}</p>
            {patient.email && (
              <p className="flex items-center gap-1.5 text-sm text-ink-muted"><Mail className="h-3.5 w-3.5" /> {patient.email}</p>
            )}
          </div>
        </div>

        <div className="mt-8 border-t border-border pt-6">
          <Link href="/appointments">
            <Button size="lg" className="w-full sm:w-auto">
              <Calendar className="h-4 w-4" />
              عرض مواعيدي
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
