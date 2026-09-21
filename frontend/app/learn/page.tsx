"use client";

import { useState } from "react";
import Link from "next/link";
import { BookOpen, ShieldCheck } from "lucide-react";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { Chip } from "@/components/ui/chip";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useKnowledgeDocuments } from "@/hooks/use-knowledge";
import { useI18n } from "@/lib/i18n/provider";

/** The approved knowledge library, in the reader's language by default. */
export default function LearnPage() {
  const { t, locale } = useI18n();
  const [language, setLanguage] = useState<"en" | "ar" | undefined>(locale);
  const { data, isLoading, isError, refetch } = useKnowledgeDocuments(language);

  return (
    <Page>
      <PageHeader title={t("learn.title")} backHref="/" />
      <h2 className="text-[25px] font-bold leading-tight text-ink">{t("learn.heading")}</h2>
      <p className="mb-4 mt-1 text-sm text-ink-muted">{t("learn.subtitle")}</p>

      <div className="mb-3 flex gap-[7px]">
        <Chip active={language === undefined} onClick={() => setLanguage(undefined)}>{t("learn.allLanguages")}</Chip>
        <Chip active={language === "en"} onClick={() => setLanguage("en")} lang="en">{t("language.en")}</Chip>
        <Chip active={language === "ar"} onClick={() => setLanguage("ar")} lang="ar">{t("language.ar")}</Chip>
      </div>

      {isLoading && <div className="grid gap-2.5 md:grid-cols-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)}</div>}
      {isError && <ErrorState onRetry={() => refetch()} />}
      {data && data.items.length === 0 && <EmptyState icon={BookOpen} title={t("learn.empty")} />}

      <div className="grid gap-2.5 md:grid-cols-2">
        {data?.items.map((doc) => (
          <Link
            key={doc.id}
            href={`/learn/${doc.id}`}
            dir={doc.language === "ar" ? "rtl" : "ltr"}
            lang={doc.language}
            className="flex gap-[11px] rounded-card border border-border bg-surface p-3 transition-colors hover:border-primary-line"
          >
            <div className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-lavender-soft text-ink">
              <BookOpen className="h-5 w-5" strokeWidth={1.75} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold text-ink">{doc.title}</p>
              {doc.summary && <p className="mt-0.5 line-clamp-2 text-xs text-ink-muted">{doc.summary}</p>}
              {doc.reviewed_by && (
                <p className="mt-1 flex items-center gap-1 text-[11px] text-sage">
                  <ShieldCheck className="h-3 w-3 shrink-0" aria-hidden="true" />
                  <span className="truncate">{doc.reviewed_by}</span>
                </p>
              )}
            </div>
          </Link>
        ))}
      </div>
    </Page>
  );
}
