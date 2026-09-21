"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { AssessmentCard } from "@/components/consultation/assessment-card";
import { SignInRequired } from "@/components/auth/sign-in-required";
import { Card } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import { getConversationIntake } from "@/services/chat-service";
import type { MessageKey } from "@/lib/i18n/types";

/**
 * The consultation summary for one conversation (the demo's "AI Result"
 * screen). Since Sprint 9 it shows the AI consultation's assessment,
 * which replaced the fixed concern → specialty lookup.
 */
function ResultContent() {
  const { t, label, formatDate } = useI18n();
  const { status, patient } = useAuth();
  const conversationId = useSearchParams().get("conversation");
  const { data: intake, isLoading, isError, refetch } = useQuery({
    queryKey: ["intake", conversationId],
    queryFn: () => getConversationIntake(conversationId as string),
    enabled: Boolean(patient && conversationId),
  });

  const header = <PageHeader title={t("result.title")} backHref="/consultation" />;
  if (status === "loading" || (patient && conversationId && isLoading)) {
    return <Page width="narrow">{header}<Skeleton className="h-96" /></Page>;
  }
  if (!patient) {
    return <Page width="narrow">{header}<SignInRequired next={`/consultation/result${conversationId ? `?conversation=${conversationId}` : ""}`} /></Page>;
  }
  if (isError) return <Page width="narrow">{header}<ErrorState onRetry={() => refetch()} /></Page>;

  const data = intake?.structured_data?.data;
  const assessment = intake?.structured_data?.assessment;
  if (!conversationId || !intake || !assessment) {
    return (
      <Page width="narrow">
        {header}
        <Card className="mt-8 text-center">
          <p className="font-bold text-ink">{t("consultation.notFinished")}</p>
          <LinkButton href="/consultation" block className="mt-4">{t("consultation.continueChat")}</LinkButton>
        </Card>
      </Page>
    );
  }

  const completedAt = intake.structured_data?.completed_at;
  const rows: [MessageKey, string | null | undefined][] = [
    ["consultation.area", data?.body_area],
    ["consultation.duration", data?.duration],
    ["consultation.symptoms", data?.symptoms ? (data.symptoms.length ? data.symptoms.join(", ") : t("consultation.noneReported")) : null],
  ];

  return (
    <Page width="narrow">
      {header}
      <div className="mx-auto mb-3 mt-4 grid h-[72px] w-[72px] place-items-center rounded-full bg-primary-soft text-primary-dark">
        <Check className="h-9 w-9" strokeWidth={2} />
      </div>
      <div className="text-center">
        <h2 className="text-xl font-bold text-ink">{t("result.heading")}</h2>
        {completedAt && <p className="mt-1 text-xs text-ink-muted">{t("consultation.completedOn", { date: formatDate(new Date(completedAt), "long") })}</p>}
      </div>

      <Card className="mt-5">
        <p className="text-xs text-ink-muted">{t("result.concern")}</p>
        <p dir="auto" className="mt-1.5 text-lg font-bold text-ink">
          {data?.concern && data.concern !== "other" ? label("concerns", data.concern) : data?.concern_detail ?? "—"}
        </p>
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
          {rows.filter(([, value]) => value).map(([key, value]) => (
            <div key={key} className="contents">
              <dt className="text-ink-muted">{t(key)}</dt>
              <dd dir="auto" className="text-ink">{value}</dd>
            </div>
          ))}
        </dl>
      </Card>

      {data?.pregnancy_or_breastfeeding && <Notice className="mt-2.5">{t("consultation.pregnancyNote")}</Notice>}

      <AssessmentCard assessment={assessment} concern={data?.concern ?? null} showSummaryLink={false} className="mt-2.5" />
      <Notice className="mt-2.5 text-xs">{t("consult.disclaimerBody")}</Notice>
    </Page>
  );
}

export default function ResultPage() {
  return (
    <Suspense fallback={<Page width="narrow"><Skeleton className="h-96" /></Page>}>
      <ResultContent />
    </Suspense>
  );
}
