"use client";

import { AlertTriangle, ClipboardCheck, ListChecks } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button, LinkButton } from "@/components/ui/button";
import { useChatActions } from "@/components/chat/chat-actions";
import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import type { Assessment, Urgency } from "@/types/chat";

const URGENCY_TONE: Record<Urgency, "sage" | "gold" | "primary"> = { routine: "sage", soon: "gold", urgent: "primary" };

/**
 * The preliminary assessment from the AI consultation (the demo's "AI
 * Result"), with the next steps. Used in the chat and on the result page.
 */
export function AssessmentCard({
  assessment,
  concern,
  conversationId,
  showSummaryLink = true,
  className,
}: {
  assessment: Assessment;
  concern: string | null;
  conversationId?: string;
  showSummaryLink?: boolean;
  className?: string;
}) {
  const { t, label } = useI18n();
  const chat = useChatActions();
  const specialty = encodeURIComponent(assessment.suggested_specialty);
  const findSlotText = t("chat.findSlotPrompt", { specialty: label("specialties", assessment.suggested_specialty) });

  return (
    <div className={cn("w-full rounded-card border border-border bg-gradient-to-br from-lavender-soft to-surface p-[14px]", className)}>
      <p className="flex items-center gap-1.5 text-sm font-bold text-ink">
        <ClipboardCheck className="h-4 w-4 text-primary-dark" aria-hidden="true" /> {t("consultation.summaryTitle")}
      </p>
      <p dir="auto" className="mt-2 text-sm leading-relaxed text-ink">{assessment.summary}</p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-xs text-ink-muted">{t("chat.suggested")}:</span>
        <span className="text-sm font-bold text-ink">{label("specialties", assessment.suggested_specialty)}</span>
      </div>
      <Badge tone={URGENCY_TONE[assessment.urgency]} className="mt-2">
        {t(`consultation.urgency.${assessment.urgency}`)}
      </Badge>

      {assessment.visit_preparation.length > 0 && (
        <div className="mt-3">
          <p className="flex items-center gap-1.5 text-xs font-bold text-ink">
            <ListChecks className="h-3.5 w-3.5" aria-hidden="true" /> {t("consultation.prepare")}
          </p>
          <ul dir="auto" className="mt-1 list-disc space-y-0.5 ps-5 text-xs text-ink-muted">
            {assessment.visit_preparation.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      )}
      {assessment.watch_for.length > 0 && (
        <div className="mt-2.5">
          <p className="flex items-center gap-1.5 text-xs font-bold text-ink">
            <AlertTriangle className="h-3.5 w-3.5 text-primary-dark" aria-hidden="true" /> {t("consultation.watchFor")}
          </p>
          <ul dir="auto" className="mt-1 list-disc space-y-0.5 ps-5 text-xs text-ink-muted">
            {assessment.watch_for.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        {/* In the chat, ask the booking agent directly; elsewhere, open the chat with the request prefilled. */}
        {chat ? (
          <Button size="sm" onClick={() => chat.send(findSlotText)}>
            {t("chat.findSlot")}
          </Button>
        ) : (
          <LinkButton size="sm" href={`/consultation?book=${specialty}`}>
            {t("chat.findSlot")}
          </LinkButton>
        )}
        <LinkButton size="sm" variant="secondary" href={`/doctors?specialty=${specialty}`}>
          {t("chat.browse")}
        </LinkButton>
        {showSummaryLink && conversationId && (
          <LinkButton size="sm" variant="ghost" href={`/consultation/result?conversation=${conversationId}`}>
            {t("consultation.viewSummary")}
          </LinkButton>
        )}
      </div>
    </div>
  );
}
