"use client";

import { useParams } from "next/navigation";
import { Info, ShieldCheck } from "lucide-react";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { Markdown } from "@/components/knowledge/markdown";
import { LinkButton } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { useKnowledgeDocument } from "@/hooks/use-knowledge";
import { useI18n } from "@/lib/i18n/provider";

/**
 * One library article. The article keeps its own language and direction
 * even inside the other-language UI. Who reviewed it (and when) is always
 * shown, so readers know how much to trust it.
 */
export default function ArticlePage() {
  const { t, formatDate } = useI18n();
  const params = useParams<{ id: string }>();
  const { data: doc, isLoading, isError, refetch } = useKnowledgeDocument(params.id);

  return (
    <Page width="narrow">
      <PageHeader title={t("learn.title")} backHref="/learn" />
      {isLoading && <Skeleton className="h-96" />}
      {(isError || (!isLoading && !doc)) && <ErrorState message={t("learn.notFound")} onRetry={() => refetch()} />}

      {doc && (
        <>
          <article dir={doc.language === "ar" ? "rtl" : "ltr"} lang={doc.language}>
            <h2 className="text-[25px] font-bold leading-tight text-ink">{doc.title}</h2>
            {doc.summary && <p className="mt-1 text-sm text-ink-muted">{doc.summary}</p>}
            <Markdown source={doc.body ?? ""} />
          </article>

          <div className="mt-6 flex flex-col gap-1 border-t border-border pt-4 text-xs text-ink-muted">
            <p className="flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-sage" aria-hidden="true" />
              {doc.reviewed_by
                ? `${t("learn.reviewedBy", { name: doc.reviewed_by })}${doc.reviewed_at ? ` ${t("learn.reviewedOn", { date: formatDate(new Date(doc.reviewed_at), "long") })}` : ""}`
                : t("learn.notReviewed")}
            </p>
            <p>
              {t("learn.source", { source: doc.source })}
              {doc.url && (
                <>
                  {" · "}
                  <a href={doc.url} target="_blank" rel="noopener noreferrer" className="text-primary-dark underline">
                    {doc.url}
                  </a>
                </>
              )}
            </p>
          </div>

          <Notice className="mt-4 flex gap-2">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-primary-dark" aria-hidden="true" />
            <p>{t("learn.disclaimer")}</p>
          </Notice>
          <LinkButton href="/consultation" block className="mt-[15px]">
            {t("learn.askAi")}
          </LinkButton>
        </>
      )}
    </Page>
  );
}
