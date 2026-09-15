import Link from "next/link";
import { Sparkles } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t border-border bg-surface">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 md:grid-cols-4 md:px-6">
        <div className="flex flex-col gap-3 md:col-span-2">
          <div className="flex items-center gap-2 text-lg font-bold text-ink">
            <Sparkles className="h-5 w-5 text-primary" strokeWidth={1.75} />
            BeautyAI
          </div>
          <p className="max-w-sm text-sm text-ink-muted">
            منصة تربط المرضى بأطباء وعيادات التجميل والجلدية الموثوقة في مصر والوطن العربي.
            BeautyAI لا تغني عن استشارة طبيب مختص.
          </p>
        </div>

        <div className="flex flex-col gap-3">
          <p className="text-sm font-semibold text-ink">استكشفي</p>
          <Link href="/doctors" className="text-sm text-ink-muted hover:text-ink">الأطباء</Link>
          <Link href="/clinics" className="text-sm text-ink-muted hover:text-ink">العيادات</Link>
          <Link href="/procedures" className="text-sm text-ink-muted hover:text-ink">الإجراءات</Link>
        </div>

        <div className="flex flex-col gap-3">
          <p className="text-sm font-semibold text-ink">حسابي</p>
          <Link href="/login" className="text-sm text-ink-muted hover:text-ink">تسجيل الدخول</Link>
          <Link href="/signup" className="text-sm text-ink-muted hover:text-ink">إنشاء حساب</Link>
          <Link href="/appointments" className="text-sm text-ink-muted hover:text-ink">مواعيدي</Link>
        </div>
      </div>
      <div className="border-t border-border px-4 py-4 text-center text-xs text-ink-muted md:px-6">
        © {new Date().getFullYear()} BeautyAI. كل الحقوق محفوظة.
      </div>
    </footer>
  );
}
