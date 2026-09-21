"use client";

import Link from "next/link";
import { BookOpen, Phone, Siren } from "lucide-react";
import { LinkButton } from "@/components/ui/button";
import { AssessmentCard } from "@/components/consultation/assessment-card";
import { BookingOptions } from "@/components/chat/booking-options";
import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types/chat";

/**
 * One chat bubble. Assistant messages are rendered by their `kind`
 * (set by the backend): a normal reply (optionally with a specialty
 * suggestion card), a fixed emergency message, or a fallback.
 * `dir="auto"` lets Arabic text render right-to-left inside the English
 * UI and vice versa.
 */
export function ChatMessageBubble({ message }: { message: ChatMessage }) {
  const { t, label } = useI18n();
  const isUser = message.role === "user";
  const extra = message.extra_data;

  if (!isUser && extra?.kind === "emergency") {
    return (
      <div role="alert" className="me-auto w-full max-w-[92%] rounded-card border border-red-200 bg-red-50 p-[14px] text-red-900">
        <p className="flex items-center gap-2 text-sm font-bold">
          <Siren className="h-4 w-4" aria-hidden="true" /> {t("chat.emergencyTitle")}
        </p>
        <p dir="auto" className="mt-1.5 whitespace-pre-line text-sm leading-relaxed">
          {message.content}
        </p>
        <a
          href="tel:123"
          className="mt-3 inline-flex h-10 items-center gap-2 rounded-xl bg-red-700 px-4 text-sm font-bold text-white hover:bg-red-800"
        >
          <Phone className="h-4 w-4" aria-hidden="true" /> {t("chat.callNow")}
        </a>
      </div>
    );
  }

  const assessment = !isUser ? extra?.assessment : null;
  // Older replies (before Sprint 9) carried only a bare suggestion.
  const suggestion = !isUser && !assessment ? extra?.suggestion : null;
  const sources = !isUser ? extra?.sources ?? [] : [];

  return (
    <div className={cn("flex max-w-[85%] flex-col gap-2", isUser ? "ms-auto items-end" : "me-auto items-start")}>
      <p
        dir="auto"
        className={cn(
          "whitespace-pre-line rounded-[18px] px-[14px] py-2.5 text-sm leading-relaxed",
          isUser ? "rounded-ee-md bg-primary text-white" : "rounded-es-md border border-border bg-surface text-ink",
          extra?.kind === "fallback" && "text-ink-muted"
        )}
      >
        {message.content}
      </p>
      {sources.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] font-semibold text-ink-muted">{t("learn.sources")}:</span>
          {sources.map((source) => (
            <Link
              key={source.document_id}
              href={`/learn/${source.document_id}`}
              dir="auto"
              className="inline-flex items-center gap-1 rounded-full border border-border bg-surface px-2.5 py-1 text-[11px] font-semibold text-primary-dark hover:border-primary-line"
            >
              <BookOpen className="h-3 w-3 shrink-0" aria-hidden="true" /> {source.title}
            </Link>
          ))}
        </div>
      )}
      {assessment && (
        <AssessmentCard assessment={assessment} concern={extra?.suggestion?.concern ?? null} conversationId={message.conversation_id} />
      )}
      {!isUser && extra?.booking && <BookingOptions offer={extra.booking} conversationId={message.conversation_id} />}
      {suggestion && (
        <div className="w-full rounded-card bg-gradient-to-br from-lavender-soft to-surface p-3">
          <p className="text-xs text-ink-muted">{t("chat.suggested")}</p>
          <p className="text-sm font-bold text-ink">{label("specialties", suggestion.specialty)}</p>
          <div className="mt-2.5 flex flex-wrap gap-2">
            <LinkButton size="sm" href={`/consultation?book=${encodeURIComponent(suggestion.specialty)}`}>
              {t("chat.findSlot")}
            </LinkButton>
            <LinkButton size="sm" variant="secondary" href={`/doctors?specialty=${encodeURIComponent(suggestion.specialty)}`}>
              {t("chat.browse")}
            </LinkButton>
          </div>
        </div>
      )}
    </div>
  );
}
