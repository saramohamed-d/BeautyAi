"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { MessageCircle } from "lucide-react";
import { Page } from "@/components/layout/page";
import { PageHeader } from "@/components/layout/page-header";
import { ChatView } from "@/components/chat/chat-view";
import { QuickGuide } from "@/components/consultation/quick-guide";
import { Card } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import { withNext } from "@/lib/safe-next";
import { isConcernId } from "@/lib/concerns";

/**
 * AI consultation. Logged-in patients chat with the AI assistant, which
 * runs the consultation (Sprints 7-9). Visitors pick a topic and are
 * invited to log in; `?topic=` then prefills the first message.
 */
function ConsultationContent() {
  const { t, label } = useI18n();
  const { status, user, patient } = useAuth();
  const searchParams = useSearchParams();
  const topic = searchParams.get("topic");
  const book = searchParams.get("book");
  // ?book=<specialty> (from a summary or old /assistant links) asks the booking agent; ?topic= starts a consultation.
  const initialText =
    book !== null
      ? t("chat.findSlotPrompt", { specialty: book ? label("specialties", book) : t("chat.anySpecialist") })
      : isConcernId(topic)
        ? t("chat.concernPrompt", { concern: t(`concerns.${topic}`) })
        : "";

  return (
    <Page width="narrow">
      <PageHeader title={t("chat.title")} backHref="/" />

      {status === "loading" ? (
        <Skeleton className="h-80" />
      ) : patient ? (
        <ChatView initialText={initialText} />
      ) : (
        <>
          {user ? (
            <Notice className="mb-4">{t("chat.staffNote")}</Notice>
          ) : (
            <Card className="mb-5 text-center">
              <div className="mx-auto mb-2 grid h-12 w-12 place-items-center rounded-full bg-lavender-soft text-ink">
                <MessageCircle className="h-5 w-5" strokeWidth={1.75} />
              </div>
              <p className="font-bold text-ink">{t("chat.loginTitle")}</p>
              <p className="mt-1 text-sm text-ink-muted">{t("chat.loginBody")}</p>
              <LinkButton href={withNext("/login", "/consultation")} block className="mt-4">
                {t("login.submit")}
              </LinkButton>
            </Card>
          )}
          {!user && (
            <>
              <h2 className="text-lg font-bold text-ink">{t("chat.quickGuideTitle")}</h2>
          <p className="mb-3 mt-1 text-sm text-ink-muted">{t("consult.subtitle")}</p>
              <QuickGuide />
            </>
          )}
          <Notice className="mt-[15px]">
            <p className="font-bold">{t("consult.disclaimerTitle")}</p>
            <p>{t("consult.disclaimerBody")}</p>
          </Notice>
        </>
      )}
    </Page>
  );
}

export default function ConsultationPage() {
  return (
    <Suspense fallback={<Page width="narrow"><Skeleton className="h-80" /></Page>}>
      <ConsultationContent />
    </Suspense>
  );
}
