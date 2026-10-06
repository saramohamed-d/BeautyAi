"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  BadgeCheck,
  CalendarCheck,
  CalendarPlus,
  CreditCard,
  HeartHandshake,
  MessageCircleHeart,
  Search,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  UserRoundSearch,
  type LucideIcon,
} from "lucide-react";
import { DoctorCard } from "@/components/doctors/doctor-card";
import { DoctorAvatar } from "@/components/doctors/doctor-avatar";
import { AppointmentCard } from "@/components/appointments/appointment-card";
import { LotusMark, Logo } from "@/components/layout/logo";
import { LanguageToggle } from "@/components/layout/language-toggle";
import { Card } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { SectionTitle } from "@/components/ui/section-title";
import { useDoctorSearch } from "@/hooks/use-doctor-search";
import { useDoctor } from "@/hooks/use-doctor";
import { useClinic } from "@/hooks/use-clinic";
import { useAppointments } from "@/hooks/use-appointments";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/types";

type Item = { icon: LucideIcon; title: MessageKey; body: MessageKey };

const HERO_POINTS: Item[] = [
  { icon: MessageCircleHeart, title: "landing.pointAiTitle", body: "landing.pointAiBody" },
  { icon: CalendarPlus, title: "landing.pointBookTitle", body: "landing.pointBookBody" },
  { icon: CreditCard, title: "landing.pointPayTitle", body: "landing.pointPayBody" },
];

const STEPS: Item[] = [
  { icon: MessageCircleHeart, title: "landing.step1Title", body: "landing.step1Body" },
  { icon: Sparkles, title: "landing.step2Title", body: "landing.step2Body" },
  { icon: UserRoundSearch, title: "landing.step3Title", body: "landing.step3Body" },
  { icon: CalendarCheck, title: "landing.step4Title", body: "landing.step4Body" },
  { icon: HeartHandshake, title: "landing.step5Title", body: "landing.step5Body" },
];

const WHY: Item[] = [
  { icon: Sparkles, title: "landing.whyAiTitle", body: "landing.whyAiBody" },
  { icon: BadgeCheck, title: "landing.whyVerifiedTitle", body: "landing.whyVerifiedBody" },
  { icon: ShieldCheck, title: "landing.whyPaymentsTitle", body: "landing.whyPaymentsBody" },
  { icon: HeartHandshake, title: "landing.whyFollowTitle", body: "landing.whyFollowBody" },
];

function IconBubble({ icon: Icon }: { icon: LucideIcon }) {
  return (
    <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-primary-soft text-primary">
      <Icon className="h-6 w-6" strokeWidth={1.6} aria-hidden="true" />
    </span>
  );
}

/** Decorative hero art: a soft circle, the AI assistant bubble and a verified-doctor card. */
function HeroArt() {
  const { t } = useI18n();
  return (
    <div className="relative mx-auto aspect-square w-full max-w-[420px]" aria-hidden="true">
      <div className="absolute inset-[6%] rounded-full bg-gradient-to-br from-blush via-primary-soft to-white" />
      <svg viewBox="0 0 200 200" className="absolute inset-0 h-full w-full text-primary-line">
        <path d="M30 150c20-10 30-30 28-55M40 160c10-25 35-35 60-30" stroke="currentColor" strokeWidth="1.2" fill="none" />
        <path d="M58 95c-8-4-12-12-10-20 8 2 13 10 10 20zM52 120c-9 0-15-6-16-14 8-1 15 5 16 14z" fill="currentColor" opacity=".55" />
        <path d="M170 60c-14 4-22 16-22 30M160 40c6 10 4 22-4 30" stroke="currentColor" strokeWidth="1.2" fill="none" />
      </svg>
      <DoctorAvatar avatar="woman-1" className="absolute left-1/2 top-1/2 h-[58%] w-[58%] -translate-x-1/2 -translate-y-1/2 ring-8 ring-white/70" />
      <div className="absolute end-0 top-[14%] w-[52%] rounded-2xl bg-white/95 p-3 text-start shadow-card">
        <p className="flex items-center gap-1.5 text-xs font-bold text-ink">
          <LotusMark className="h-5 w-5" /> {t("landing.artAssistant")}
        </p>
        <p className="mt-1 text-[11px] leading-snug text-ink-muted">{t("landing.artAssistantBody")}</p>
      </div>
      <div className="absolute bottom-[10%] start-0 flex items-center gap-2 rounded-2xl bg-white/95 p-2.5 pe-4 shadow-card">
        <span className="grid h-8 w-8 place-items-center rounded-full bg-sage-soft text-sage">
          <BadgeCheck className="h-4 w-4" />
        </span>
        <span className="text-xs font-bold text-ink">{t("landing.artVerified")}</span>
      </div>
      <p className="absolute -top-1 start-[4%] -rotate-6 font-display text-lg italic text-primary-accent">{t("landing.artScript")}</p>
    </div>
  );
}

/** Logged-in patients see their next visit right under the hero. */
function UpcomingAppointment() {
  const { t } = useI18n();
  const { patient } = useAuth();
  const { data, isLoading } = useAppointments({ patient_id: patient?.id, page_size: 50 });

  const now = new Date();
  const next = data?.items
    .filter((a) => a.status !== "cancelled" && new Date(a.scheduled_start) >= now)
    .sort((a, b) => +new Date(a.scheduled_start) - +new Date(b.scheduled_start))[0];

  const { data: doctor } = useDoctor(next?.doctor_id);
  const { data: clinic } = useClinic(next?.clinic_id);

  if (isLoading) return <Skeleton className="h-[84px]" />;
  if (!next) {
    return (
      <Card className="flex items-center justify-between gap-3">
        <p className="text-sm text-ink-muted">{t("home.noUpcoming")}</p>
        <LinkButton href="/doctors" size="sm" variant="secondary" className="shrink-0">
          {t("home.bookVisit")}
        </LinkButton>
      </Card>
    );
  }
  return (
    <AppointmentCard
      appointment={next}
      doctorName={doctor?.full_name ?? "—"}
      doctorAvatar={doctor?.avatar}
      clinicName={clinic?.name ?? "—"}
    />
  );
}

export default function HomePage() {
  const { t } = useI18n();
  const router = useRouter();
  const { patient } = useAuth();
  const [query, setQuery] = useState("");
  const { data: doctorsData, isLoading: doctorsLoading } = useDoctorSearch({ page_size: 4 });

  function onSearch(event: FormEvent) {
    event.preventDefault();
    const q = query.trim();
    router.push(q ? `/doctors?q=${encodeURIComponent(q)}` : "/doctors");
  }

  return (
    <div className="pb-28 md:pb-0">
      {/* Hero */}
      <section className="bg-gradient-to-b from-white to-bg">
        <div className="mx-auto grid max-w-6xl items-center gap-8 px-[18px] pb-10 pt-8 md:grid-cols-[1.1fr_1fr] md:px-6 md:pb-16 md:pt-14">
          <div>
            {/* Phones have no top bar: logo and language switch sit above the hero. */}
            <div className="mb-6 flex items-center justify-between md:hidden">
              <Logo />
              <LanguageToggle />
            </div>
            <p className="text-sm font-semibold text-primary-dark">{t("landing.eyebrow")}</p>
            {patient && <p className="mt-1 text-sm text-ink-muted">{t("landing.welcomeBack", { name: patient.full_name.split(" ")[0] ?? "" })}</p>}
            <h1 className="mt-3 font-display text-[40px] font-semibold leading-[1.08] text-ink md:text-[58px]">
              {t("landing.titleLine1")}
              <br />
              {t("landing.titleLine2")}
              <br />
              <span className="text-primary">{t("landing.titleLine3")}</span>
            </h1>
            <p className="mt-4 max-w-md text-[15px] leading-relaxed text-ink-muted">{t("landing.subtitle")}</p>

            <div className="mt-6 flex flex-wrap gap-3">
              <LinkButton href={patient ? "/consultation" : "/signup"} className="rounded-full px-7">
                {t("landing.start")} <ArrowRight className="h-4 w-4 rtl:rotate-180" />
              </LinkButton>
              <LinkButton href="/doctors" variant="secondary" className="rounded-full px-7">
                <Stethoscope className="h-4 w-4" /> {t("landing.findDoctor")}
              </LinkButton>
            </div>

            <form onSubmit={onSearch} role="search" className="mt-6 flex h-12 max-w-md items-center gap-2 rounded-full border border-border bg-surface ps-5 pe-1.5 shadow-card">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("home.searchPlaceholder")}
                aria-label={t("home.searchLabel")}
                className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-ink-muted/80"
              />
              <button type="submit" aria-label={t("home.searchLabel")} className="grid h-9 w-9 place-items-center rounded-full bg-primary text-white hover:bg-primary-dark">
                <Search className="h-4 w-4" />
              </button>
            </form>

            <ul className="mt-8 grid grid-cols-3 gap-3">
              {HERO_POINTS.map(({ icon: Icon, title, body }) => (
                <li key={title} className="flex flex-col gap-2 md:flex-row md:items-start">
                  <Icon className="h-6 w-6 shrink-0 text-primary" strokeWidth={1.6} aria-hidden="true" />
                  <span>
                    <span className="block text-xs font-bold text-ink">{t(title)}</span>
                    <span className="block text-[11px] leading-snug text-ink-muted">{t(body)}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <HeroArt />
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-[18px] md:px-6">
        {patient && (
          <section className="md:max-w-xl">
            <SectionTitle title={t("home.upcoming")} href="/appointments" linkLabel={t("common.viewAll")} />
            <UpcomingAppointment />
          </section>
        )}

        {/* How it works */}
        <section id="how-it-works" className="scroll-mt-24 py-12">
          <h2 className="font-display text-3xl font-semibold text-ink">{t("landing.howTitle")}</h2>
          <p className="mt-1 text-sm text-ink-muted">{t("landing.howSubtitle")}</p>
          <ol className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-5">
            {STEPS.map(({ icon, title, body }, index) => (
              <li key={title} className="relative flex items-start gap-3 md:flex-col md:items-center md:text-center">
                <IconBubble icon={icon} />
                {index < STEPS.length - 1 && (
                  <span aria-hidden="true" className="absolute start-[calc(50%+36px)] top-6 hidden h-px w-[calc(100%-72px)] border-t border-dashed border-primary-line md:block" />
                )}
                <span>
                  <span className="block text-sm font-bold text-ink">
                    {index + 1}. {t(title)}
                  </span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-ink-muted">{t(body)}</span>
                </span>
              </li>
            ))}
          </ol>
        </section>

        {/* Recommended doctors */}
        <section className="pb-12">
          <div className="flex items-end justify-between gap-3">
            <div>
              <h2 className="font-display text-3xl font-semibold text-ink">{t("landing.doctorsTitle")}</h2>
              <p className="mt-1 text-sm text-ink-muted">{t("landing.doctorsSubtitle")}</p>
            </div>
            <LinkButton href="/doctors" size="sm" variant="secondary" className="shrink-0">
              {t("common.viewAll")}
            </LinkButton>
          </div>
          <div className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-2">
            {doctorsLoading && Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-[112px]" />)}
            {doctorsData?.items.map(({ doctor, next_slot, price_from, clinics }) => (
              <DoctorCard key={doctor.id} doctor={doctor} nextSlot={next_slot} priceFrom={price_from} clinics={clinics} />
            ))}
          </div>
        </section>

        {/* AI consultation callout */}
        <section className="mb-12 grid items-center gap-6 overflow-hidden rounded-[28px] bg-gradient-to-br from-blush via-primary-soft to-white p-6 md:grid-cols-[1fr_auto] md:p-10">
          <div>
            <h2 className="font-display text-3xl font-semibold text-ink">{t("landing.moreTitle")}</h2>
            <p className="mt-2 max-w-lg text-sm leading-relaxed text-ink-muted">{t("landing.moreBody")}</p>
            <LinkButton href="/consultation" className="mt-5 rounded-full px-7">
              <Sparkles className="h-4 w-4" /> {t("landing.moreCta")}
            </LinkButton>
          </div>
          <div className="hidden h-36 w-36 place-items-center rounded-full bg-white/80 shadow-card md:grid">
            <LotusMark className="h-20 w-20" />
          </div>
        </section>

        {/* Why choose */}
        <section className="pb-14">
          <h2 className="font-display text-3xl font-semibold text-ink">{t("landing.whyTitle")}</h2>
          <ul className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
            {WHY.map(({ icon, title, body }) => (
              <li key={title} className="rounded-card border border-border bg-surface p-5 shadow-card">
                <IconBubble icon={icon} />
                <p className="mt-3 text-sm font-bold text-ink">{t(title)}</p>
                <p className="mt-1 text-xs leading-relaxed text-ink-muted">{t(body)}</p>
              </li>
            ))}
          </ul>
          <div className="mt-6 flex flex-col items-center justify-between gap-4 rounded-card bg-surface p-6 text-center shadow-card md:flex-row md:text-start">
            <p className="font-display text-2xl italic text-primary-dark">{t("landing.ctaScript")}</p>
            <LinkButton href={patient ? "/doctors" : "/signup"} className="rounded-full px-7">
              {t("landing.ctaButton")} <ArrowRight className="h-4 w-4 rtl:rotate-180" />
            </LinkButton>
          </div>
        </section>
      </div>
    </div>
  );
}
