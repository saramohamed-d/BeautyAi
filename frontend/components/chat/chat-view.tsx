"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Info, Plus, SendHorizontal } from "lucide-react";
import { AssistantIcon, ChatMessageBubble } from "@/components/chat/chat-message";
import { ChatActionsContext } from "@/components/chat/chat-actions";
import { ConsultationProgress } from "@/components/consultation/consultation-progress";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Notice } from "@/components/ui/notice";
import { Skeleton } from "@/components/ui/skeleton";
import { CONCERNS } from "@/lib/concerns";
import { useI18n } from "@/lib/i18n/provider";
import { ApiError } from "@/lib/api-client";
import {
  getConversation,
  getConversationIntake,
  listConversations,
  sendChatMessage,
  startConversation,
} from "@/services/chat-service";
import { REQUIRED_FIELDS, type ChatMessage, type Conversation } from "@/types/chat";

type ChatError = "consent" | "rate" | "failed";
const MAX_CHARS = 2000;
/** After this long the "thinking" line explains that the (local) AI can be slow. */
const SLOW_AFTER_SECONDS = 8;

/** Seconds since `since` was set, ticking once a second; 0 while it's null. */
function useElapsed(since: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (since === null) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [since]);
  return since === null ? 0 : Math.max(0, Math.floor((now - since) / 1000));
}

/**
 * The patient's AI consultation. Resumes the latest open conversation; a
 * new one is created on the first message (after the one-time AI terms
 * checkbox). Every message goes through POST /conversations/{id}/chat,
 * where the backend screens it for emergencies before any AI sees it and
 * tracks the consultation checklist shown in the progress bar.
 */
export function ChatView({ initialText = "" }: { initialText?: string }) {
  const { t, locale } = useI18n();
  const [loading, setLoading] = useState(true);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [hasPastConversations, setHasPastConversations] = useState(false);
  const [needsConsent, setNeedsConsent] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [text, setText] = useState(initialText);
  // Required consultation details still missing; null once the consultation is complete.
  const [missing, setMissing] = useState<string[] | null>([...REQUIRED_FIELDS]);
  const [pending, setPending] = useState<string | null>(null);
  const [pendingSince, setPendingSince] = useState<number | null>(null);
  const elapsed = useElapsed(pendingSince);
  const [error, setError] = useState<ChatError | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const latest = (await listConversations({ page_size: 1 })).items[0];
        if (cancelled) return;
        setHasPastConversations(Boolean(latest));
        if (latest && latest.status !== "completed") {
          const [detail, intake] = await Promise.all([getConversation(latest.id), getConversationIntake(latest.id)]);
          if (cancelled) return;
          setConversation(detail);
          setMessages(detail.messages);
          if (intake) setMissing(intake.status === "complete" ? null : intake.missing_fields ?? []);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, pending]);

  const showConsent = !conversation && (!hasPastConversations || needsConsent);
  const isDemo = messages.some((m) => m.extra_data?.ai?.provider === "demo");

  async function send(content: string) {
    const trimmed = content.trim();
    if (!trimmed || pending) return;
    setError(null);

    let active = conversation;
    if (!active) {
      if (showConsent && !accepted) {
        setError("consent");
        return;
      }
      try {
        active = await startConversation({ accept_ai_terms: accepted, language: locale });
        setConversation(active);
        setHasPastConversations(true);
      } catch (err) {
        if (err instanceof ApiError && err.code === "consent_required") {
          setNeedsConsent(true);
          setError("consent");
        } else {
          setError("failed");
        }
        return;
      }
    }

    setPending(trimmed);
    setPendingSince(Date.now());
    setText("");
    try {
      const turn = await sendChatMessage(active.id, trimmed);
      setMessages((prev) => [...prev, turn.user_message, turn.assistant_message]);
      setConversation((prev) => (prev ? { ...prev, status: turn.conversation_status } : prev));
      if (turn.consultation) setMissing(turn.consultation.status === "complete" ? null : turn.consultation.missing_fields);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 429 ? "rate" : "failed");
      setText(trimmed);
    } finally {
      setPending(null);
      setPendingSince(null);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(text);
  }

  if (loading) return <Skeleton className="h-80" />;

  return (
    <ChatActionsContext.Provider value={{ send: (value: string) => void send(value) }}>
    <div className="flex flex-col">
      <div className="-mx-[18px] mb-4 flex items-center gap-3 bg-gradient-to-r from-blush to-lavender-soft px-[18px] py-4 md:mx-0 md:rounded-card md:px-5">
        <AssistantIcon className="h-12 w-12" />
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-bold text-ink">{t("chat.assistantName")}</h2>
          <p className="text-xs text-ink-muted">{t("chat.assistantTagline")}</p>
        </div>
        {conversation && (
          <Button
            size="sm"
            variant="ghost"
            className="shrink-0"
            onClick={() => {
              setConversation(null);
              setMessages([]);
              setError(null);
              setMissing([...REQUIRED_FIELDS]);
            }}
          >
            <Plus className="h-4 w-4" /> {t("chat.newChat")}
          </Button>
        )}
      </div>
      <p className="mb-3 flex items-center gap-1.5 text-xs text-ink-muted">
        <Info className="h-3.5 w-3.5 shrink-0" aria-hidden="true" /> {t("chat.disclaimer")}
      </p>

      {/* Shown once the consultation has started; a patient who only wants to book never sees "0 of 4". */}
      {conversation && missing && missing.length < REQUIRED_FIELDS.length && <ConsultationProgress missing={missing} />}

      {isDemo && (
        <Badge tone="lavender" className="mb-3 self-start" title={t("chat.demoHint")}>
          {t("chat.demo")} · {t("chat.demoHint")}
        </Badge>
      )}

      {messages.length === 0 && !pending && (
        <div className="mb-4 text-center">
          <h2 className="mt-2 font-display text-2xl font-semibold text-ink">{t("chat.welcomeTitle")}</h2>
          <p className="mx-auto mt-1 max-w-sm text-sm text-ink-muted">{t("chat.welcomeBody")}</p>

          {showConsent && (
            <Notice className="mt-4 text-start">
              <label className="flex cursor-pointer items-start gap-2.5">
                <input
                  type="checkbox"
                  checked={accepted}
                  onChange={(e) => {
                    setAccepted(e.target.checked);
                    if (e.target.checked && error === "consent") setError(null);
                  }}
                  className="mt-0.5 h-4 w-4 shrink-0 accent-primary"
                />
                <span>{t("chat.consent")}</span>
              </label>
            </Notice>
          )}

          <p className="mb-2 mt-5 text-xs font-semibold text-ink-muted">{t("chat.quickStart")}</p>
          <div className="flex flex-wrap justify-center gap-[7px]">
            {CONCERNS.map(({ id }) => (
              <Chip key={id} onClick={() => send(t("chat.concernPrompt", { concern: t(`concerns.${id}`) }))}>
                {t(`concerns.${id}`)}
              </Chip>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-col gap-3" aria-live="polite">
        {messages.map((message) => (
          <ChatMessageBubble key={message.id} message={message} />
        ))}
        {pending && (
          <>
            <p dir="auto" className="ms-auto max-w-[85%] whitespace-pre-line rounded-[18px] rounded-ee-md bg-primary px-[14px] py-2.5 text-sm text-white opacity-80">
              {pending}
            </p>
            <div className="me-auto flex items-end gap-2">
              <AssistantIcon className="h-8 w-8" />
              <div className="rounded-[18px] rounded-es-md border border-border bg-surface px-[14px] py-2.5 text-xs text-ink-muted" role="status">
                <p className="flex items-center gap-2">
                  <span className="flex gap-1" aria-hidden="true">
                    {[0, 150, 300].map((delay) => (
                      <span key={delay} className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary-accent" style={{ animationDelay: `${delay}ms` }} />
                    ))}
                  </span>
                  {t("chat.typing")}
                  {elapsed > 0 && <span className="tabular-nums">{t("chat.elapsed", { seconds: elapsed })}</span>}
                </p>
                {elapsed >= SLOW_AFTER_SECONDS && <p className="mt-1">{t("chat.slowHint")}</p>}
              </div>
            </div>
          </>
        )}
        {conversation?.status === "escalated" && <Notice className="text-xs">{t("chat.escalated")}</Notice>}
        <div ref={endRef} />
      </div>

      {error && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {error === "consent" ? t("chat.consentRequired") : error === "rate" ? t("chat.rateLimited") : t("chat.sendFailed")}
        </p>
      )}

      <form
        onSubmit={onSubmit}
        className="sticky bottom-[88px] mt-4 flex items-end gap-2 rounded-full border border-border bg-surface p-1.5 ps-3 shadow-card focus-within:border-primary md:bottom-4"
      >
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              void send(text);
            }
          }}
          rows={1}
          maxLength={MAX_CHARS}
          dir="auto"
          placeholder={t("chat.placeholder")}
          aria-label={t("chat.placeholder")}
          className="max-h-32 min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-ink-muted/80 focus-visible:outline-none"
        />
        <Button type="submit" size="sm" className="h-10 w-10 shrink-0 rounded-full px-0" disabled={!text.trim() || Boolean(pending)} aria-label={t("chat.send")}>
          <SendHorizontal className="h-4 w-4 rtl:rotate-180" />
        </Button>
      </form>
    </div>
    </ChatActionsContext.Provider>
  );
}
