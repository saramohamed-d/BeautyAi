"use client";

import Link from "next/link";
import { CalendarCheck, MapPin, ShieldCheck, Sparkles, Stethoscope } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DoctorCard } from "@/components/doctors/doctor-card";
import { ClinicCard } from "@/components/clinics/clinic-card";
import { SectionHeading } from "@/components/ui/section-heading";
import { Skeleton } from "@/components/ui/skeleton";
import { useDoctors } from "@/hooks/use-doctors";
import { useClinics } from "@/hooks/use-clinics";

const CONCERNS = [
  { label: "الحقن التجميلي", category: "injectable" },
  { label: "إزالة الشعر بالليزر", category: "laser" },
  { label: "العناية بالبشرة", category: "skin_treatment" },
];

const STEPS = [
  { title: "اختاري طبيبك", description: "تصفّحي الأطباء الموثّقين حسب التخصص والخبرة." },
  { title: "احجزي معادك", description: "اختاري العيادة والتاريخ والوقت المناسب لك." },
  { title: "استشيري بثقة", description: "احصلي على رعاية تجميلية وجلدية من عيادات معتمدة." },
];

/**
 * Homepage — the one place in the app that spends a deliberate motion
 * moment (a single fade/slide entrance on the hero, respecting
 * prefers-reduced-motion via globals.css), rather than animating every
 * card on scroll.
 */
export default function HomePage() {
  const { data: doctorsData, isLoading: doctorsLoading } = useDoctors({ page_size: 3, is_active: true });
  const { data: clinicsData, isLoading: clinicsLoading } = useClinics({ page_size: 3 });

  return (
    <div className="flex flex-col gap-20 pb-20 pt-10 md:gap-28 md:pt-16">
      {/* Hero */}
      <section className="mx-auto grid max-w-6xl items-center gap-10 px-4 md:grid-cols-2 md:px-6">
        <div className="motion-safe:animate-[fadeIn_0.6s_ease-out] flex flex-col gap-6">
          <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-primary-soft px-3 py-1 text-sm font-medium text-primary-dark">
            <Sparkles className="h-3.5 w-3.5" />
            رعاية تجميلية وجلدية موثوقة
          </span>
          <h1 className="text-4xl font-bold leading-tight text-ink md:text-5xl">
            بشرتك تستحق دكتور تثقي فيه
          </h1>
          <p className="max-w-md text-lg text-ink-muted">
            BeautyAI بتوصّلك بأفضل أطباء وعيادات التجميل والجلدية في مصر، وتساعدك تحجزي معادك في دقايق.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link href="/booking">
              <Button size="lg">احجزي موعدك الآن</Button>
            </Link>
            <Link href="/doctors">
              <Button size="lg" variant="outline">تصفّحي الأطباء</Button>
            </Link>
          </div>
          <dl className="mt-4 flex flex-wrap gap-8 text-sm text-ink-muted">
            <div>
              <dt className="sr-only">أطباء موثّقون</dt>
              <dd className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-sage" /> أطباء موثّقون</dd>
            </div>
            <div>
              <dt className="sr-only">عيادات في القاهرة والجيزة</dt>
              <dd className="flex items-center gap-2"><MapPin className="h-4 w-4 text-primary" /> عيادات في القاهرة والجيزة</dd>
            </div>
          </dl>
        </div>

        {/* Abstract soft-blob illustration — deliberately not a stock photo */}
        <div className="relative mx-auto hidden aspect-square w-full max-w-md md:block" aria-hidden="true">
          <svg viewBox="0 0 400 400" className="h-full w-full">
            <path
              fill="#F3E1E6"
              d="M311.5 74.5Q347 149 341.5 213.5Q336 278 279 322Q222 366 156 344.5Q90 323 63 258.5Q36 194 68 130Q100 66 168 46Q236 26 273.5 50Q311 74 311.5 74.5Z"
            />
            <circle cx="200" cy="200" r="70" fill="#F3EAD9" />
            <circle cx="230" cy="170" r="26" fill="#9C5B6E" opacity="0.85" />
          </svg>
        </div>
      </section>

      {/* Quick concerns */}
      <section className="mx-auto w-full max-w-6xl px-4 md:px-6">
        <div className="flex flex-wrap gap-3">
          {CONCERNS.map((concern) => (
            <Link
              key={concern.category}
              href={`/procedures?category=${concern.category}`}
              className="rounded-full border border-border bg-surface px-5 py-2.5 text-sm font-medium text-ink hover:border-primary hover:text-primary-dark"
            >
              {concern.label}
            </Link>
          ))}
        </div>
      </section>

      {/* How it works — a genuine sequence, so numbering is earned here */}
      <section className="mx-auto w-full max-w-6xl px-4 md:px-6">
        <SectionHeading title="رحلتك معنا في 3 خطوات" />
        <div className="mt-8 grid gap-6 md:grid-cols-3">
          {STEPS.map((step, index) => (
            <div key={step.title} className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-6">
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-sm font-semibold text-white">
                {index + 1}
              </span>
              <p className="font-semibold text-ink">{step.title}</p>
              <p className="text-sm text-ink-muted">{step.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Featured doctors */}
      <section className="mx-auto w-full max-w-6xl px-4 md:px-6">
        <div className="flex items-end justify-between">
          <SectionHeading eyebrow="نخبة الأطباء" title="أطباء موثّقون بانتظارك" />
          <Link href="/doctors" className="hidden text-sm font-medium text-primary md:block">عرض الكل</Link>
        </div>
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {doctorsLoading &&
            Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-48" />)}
          {doctorsData?.items.map((doctor) => (
            <DoctorCard key={doctor.id} doctor={doctor} />
          ))}
        </div>
      </section>

      {/* Featured clinics */}
      <section className="mx-auto w-full max-w-6xl px-4 md:px-6">
        <div className="flex items-end justify-between">
          <SectionHeading eyebrow="أماكن موثوقة" title="عيادات معتمدة قريبة منك" />
          <Link href="/clinics" className="hidden text-sm font-medium text-primary md:block">عرض الكل</Link>
        </div>
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {clinicsLoading &&
            Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-40" />)}
          {clinicsData?.items.map((clinic) => (
            <ClinicCard key={clinic.id} clinic={clinic} />
          ))}
        </div>
      </section>

      {/* CTA band */}
      <section className="mx-auto w-full max-w-6xl px-4 md:px-6">
        <div className="flex flex-col items-center gap-5 rounded-3xl bg-primary px-6 py-14 text-center text-white">
          <CalendarCheck className="h-8 w-8" strokeWidth={1.5} />
          <h2 className="text-2xl font-semibold md:text-3xl">مستعدة تبدئي رحلتك؟</h2>
          <p className="max-w-md text-primary-soft/90">
            احجزي استشارتك الأولى مع أحد أطبائنا الموثّقين في أقل من خمس دقائق.
          </p>
          <Link href="/booking">
            <Button size="lg" variant="secondary" className="bg-white text-primary hover:bg-primary-soft">
              <Stethoscope className="h-4 w-4" />
              ابدئي الحجز
            </Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
