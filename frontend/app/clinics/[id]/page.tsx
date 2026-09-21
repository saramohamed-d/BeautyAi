"use client";

import { useParams } from "next/navigation";
import { Building2, Mail, MapPin, Phone } from "lucide-react";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { useClinic } from "@/hooks/use-clinic";
import { useI18n } from "@/lib/i18n/provider";

export default function ClinicDetailPage() {
  const { t } = useI18n();
  const params = useParams<{ id: string }>();
  const { data: clinic, isLoading, isError, refetch } = useClinic(params.id);

  return (
    <Page width="narrow">
      <PageHeader title={t("clinics.detailTitle")} />

      {isLoading && <Skeleton className="h-72" />}
      {(isError || (!isLoading && !clinic)) && <ErrorState message={t("errors.clinicNotFound")} onRetry={() => refetch()} />}

      {clinic && (
        <>
          <div className="text-center">
            <div className="mx-auto my-6 grid h-[82px] w-[82px] place-items-center rounded-[28px] bg-sage-soft text-sage">
              <Building2 className="h-9 w-9" strokeWidth={1.5} />
            </div>
            <h2 className="text-xl font-bold text-ink">{clinic.name}</h2>
            <p className="mt-1 flex items-center justify-center gap-1 text-xs text-ink-muted">
              <MapPin className="h-3.5 w-3.5" />
              {clinic.address ? `${clinic.address} · ` : ""}
              {clinic.city}
            </p>
          </div>

          {clinic.description && (
            <Card className="mt-5">
              <p className="text-sm leading-relaxed text-ink-muted">{clinic.description}</p>
            </Card>
          )}

          {(clinic.phone || clinic.email) && (
            <Card className="mt-2.5">
              <p className="text-sm font-bold text-ink">{t("clinics.contact")}</p>
              <div className="mt-1 flex flex-col gap-1 text-sm text-ink-muted">
                {clinic.phone && (
                  <a href={`tel:${clinic.phone}`} className="flex items-center gap-1.5 hover:text-ink">
                    <Phone className="h-4 w-4 text-primary-dark" /> <span dir="ltr">{clinic.phone}</span>
                  </a>
                )}
                {clinic.email && (
                  <a href={`mailto:${clinic.email}`} className="flex items-center gap-1.5 hover:text-ink">
                    <Mail className="h-4 w-4 text-primary-dark" /> {clinic.email}
                  </a>
                )}
              </div>
            </Card>
          )}

          <p className="mt-5 text-center text-sm text-ink-muted">{t("clinics.bookHint")}</p>
          <LinkButton href="/doctors" block className="mt-3">
            {t("clinics.browseDoctors")}
          </LinkButton>
        </>
      )}
    </Page>
  );
}
