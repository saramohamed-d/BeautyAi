"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { BookOpen, Building2, CalendarPlus, Search, Sparkle, Sparkles, Stethoscope, type LucideIcon } from "lucide-react";
import { Page } from "@/components/layout/page";
import { LanguageToggle } from "@/components/layout/language-toggle";
import { DoctorCard } from "@/components/doctors/doctor-card";
import { AppointmentCard } from "@/components/appointments/appointment-card";
import { Card } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { SectionTitle } from "@/components/ui/section-title";
import { Skeleton } from "@/components/ui/skeleton";
import { useDoctorSearch } from "@/hooks/use-doctor-search";
import { useDoctor } from "@/hooks/use-doctor";
import { useClinic } from "@/hooks/use-clinic";
import { useAppointments } from "@/hooks/use-appointments";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/types";
import { cn } from "@/lib/utils";

const TILES: { href: string; title: MessageKey; sub: MessageKey; icon: LucideIcon; tone: string }[] = [
  { href: "/consultation", title: "home.tiles.aiTitle", sub: "home.tiles.aiSub", icon: Sparkles, tone: "bg-lavender-soft" },
  { href: "/booking", title: "home.tiles.bookTitle", sub: "home.tiles.bookSub", icon: CalendarPlus, tone: "bg-primary-soft" },
  { href: "/doctors", title: "home.tiles.doctorsTitle", sub: "home.tiles.doctorsSub", icon: Stethoscope, tone: "bg-sage-soft" },
];

/** Time-of-day greeting, computed after mount so server and client HTML match. */
function useGreeting(): MessageKey {
  const [key, setKey] = useState<MessageKey>("home.morning");
  useEffect(() => {
    const hour = new Date().getHours();
    setKey(hour < 12 ? "home.morning" : hour < 18 ? "home.afternoon" : "home.evening");
  }, []);
  return key;
}

function UpcomingAppointment() {
  const { t } = useI18n();
  const { status, patient } = useAuth();
  const { data, isLoading } = useAppointments({ patient_id: patient?.id, page_size: 50 });

  const now = new Date();
  const next = data?.items
    .filter((a) => a.status !== "cancelled" && new Date(a.scheduled_start) >= now)
    .sort((a, b) => +new Date(a.scheduled_start) - +new Date(b.scheduled_start))[0];

  const { data: doctor } = useDoctor(next?.doctor_id);
  const { data: clinic } = useClinic(next?.clinic_id);

  if (status === "loading") return <Skeleton className="h-[76px]" />;
  if (!patient) {
    return (
      <Card className="flex items-center justify-between gap-3">
        <p className="text-sm text-ink-muted">{t("home.signInForAppointments")}</p>
        <LinkButton href="/login" size="sm" variant="secondary" className="shrink-0">
          {t("nav.signIn")}
        </LinkButton>
      </Card>
    );
  }
  if (isLoading) return <Skeleton className="h-[76px]" />;
  if (!next) {
    return (
      <Card className="flex items-center justify-between gap-3">
        <p className="text-sm text-ink-muted">{t("home.noUpcoming")}</p>
        <LinkButton href="/booking" size="sm" variant="secondary" className="shrink-0">
          {t("home.bookVisit")}
        </LinkButton>
      </Card>
    );
  }
  return <AppointmentCard appointment={next} doctorName={doctor?.full_name ?? "—"} clinicName={clinic?.name ?? "—"} />;
}

export default function HomePage() {
  const { t } = useI18n();
  const router = useRouter();
  const { patient } = useAuth();
  const greeting = useGreeting();
  const [query, setQuery] = useState("");
  const { data: doctorsData, isLoading: doctorsLoading } = useDoctorSearch({ page_size: 4 });

  function onSearch(event: FormEvent) {
    event.preventDefault();
    const q = query.trim();
    router.push(q ? `/doctors?q=${encodeURIComponent(q)}` : "/doctors");
  }

  return (
    <Page>
      <div className="flex items-start gap-3">
        <div className="flex-1">
          <h1 className="text-[25px] font-bold leading-tight text-ink md:text-3xl">
            {t(greeting)}
            {patient && (
              <>
                {t("common.comma")}
                <br />
                {patient.full_name.split(" ")[0]}
              </>
            )}{" "}
            👋
          </h1>
          <p className="mt-1 text-sm text-ink-muted">{t("home.subtitle")}</p>
        </div>
        <LanguageToggle className="md:hidden" />
      </div>

      <form onSubmit={onSearch} role="search" className="my-[18px] flex h-12 items-center gap-2 rounded-tile border border-border bg-surface px-[14px] md:max-w-xl">
        <Search className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden="true" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("home.searchPlaceholder")}
          aria-label={t("home.searchLabel")}
          className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-ink-muted/80"
        />
      </form>

      <div className="grid grid-cols-3 gap-[9px] md:max-w-xl">
        {TILES.map(({ href, title, sub, icon: Icon, tone }) => (
          <Link
            key={href}
            href={href}
            className={cn("flex min-h-[135px] flex-col items-center rounded-card px-[7px] py-3 text-center transition-transform hover:-translate-y-0.5", tone)}
          >
            <Icon className="mt-2 h-6 w-6 text-ink" strokeWidth={1.5} />
            <span className="mt-3 text-xs font-bold text-ink">{t(title)}</span>
            <span className="mt-1 text-[11px] leading-snug text-ink-muted">{t(sub)}</span>
          </Link>
        ))}
      </div>

      <div className="mt-3 flex gap-2">
        <Link href="/clinics" className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-surface px-3 py-2 text-xs font-semibold text-ink hover:border-primary-line">
          <Building2 className="h-3.5 w-3.5 text-sage" /> {t("nav.clinics")}
        </Link>
        <Link href="/procedures" className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-surface px-3 py-2 text-xs font-semibold text-ink hover:border-primary-line">
          <Sparkle className="h-3.5 w-3.5 text-primary-dark" /> {t("nav.procedures")}
        </Link>
        <Link href="/learn" className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-surface px-3 py-2 text-xs font-semibold text-ink hover:border-primary-line">
          <BookOpen className="h-3.5 w-3.5 text-ink" /> {t("nav.learn")}
        </Link>
      </div>

      <div className="md:grid md:grid-cols-2 md:gap-8">
        <section>
          <SectionTitle title={t("home.upcoming")} href={patient ? "/appointments" : undefined} linkLabel={t("common.viewAll")} />
          <UpcomingAppointment />

          <SectionTitle title={t("home.aiSection")} href="/consultation" linkLabel={t("home.aiLink")} />
          <Notice>
            <p className="font-bold">{t("home.noticeTitle")}</p>
            <p className="mt-1">{t("home.noticeBody")}</p>
            <LinkButton href="/consultation" block className="mt-[15px]">
              {t("home.noticeCta")}
            </LinkButton>
          </Notice>
        </section>

        <section>
          <SectionTitle title={t("home.topDoctors")} href="/doctors" linkLabel={t("common.viewAll")} />
          <div className="flex flex-col gap-2.5">
            {doctorsLoading && Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-[76px]" />)}
            {doctorsData?.items.map(({ doctor, next_slot }) => (
              <DoctorCard key={doctor.id} doctor={doctor} nextSlot={next_slot} />
            ))}
          </div>
        </section>
      </div>
    </Page>
  );
}
