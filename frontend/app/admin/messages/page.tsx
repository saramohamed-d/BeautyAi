"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { AdminShell } from "@/components/admin/admin-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useI18n } from "@/lib/i18n/provider";
import { LIVE } from "@/lib/query-options";
import { dispatchNotifications, fetchNotifications } from "@/services/admin-service";
import type { NotificationStatus } from "@/types/admin";

const FILTERS: (NotificationStatus | "all")[] = ["all", "pending", "sent", "failed", "skipped", "cancelled"];
const TONES: Record<NotificationStatus, "primary" | "sage" | "neutral"> = {
  pending: "primary",
  sent: "sage",
  failed: "primary",
  skipped: "neutral",
  cancelled: "neutral",
};

/** Every message the platform has written, and a button to send what's due (Sprint 15). */
export default function AdminMessagesPage() {
  return <AdminShell>{() => <Messages />}</AdminShell>;
}

function Messages() {
  const { t, formatDate, formatTime, label } = useI18n();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<NotificationStatus | "all">("all");
  const [result, setResult] = useState<string | null>(null);

  const messages = useQuery({
    queryKey: ["admin-notifications", filter],
    queryFn: () => fetchNotifications({ page_size: 100, ...(filter === "all" ? {} : { status: filter }) }),
    ...LIVE,
  });

  const dispatch = useMutation({
    mutationFn: dispatchNotifications,
    onSuccess: (counts) => {
      setResult(t("admin.messages.dispatched", { sent: counts.sent, failed: counts.failed }));
      queryClient.invalidateQueries({ queryKey: ["admin-notifications"] });
    },
  });

  const items = messages.data?.items ?? [];

  return (
    <>
      <h2 className="text-lg font-bold text-ink">{t("admin.messages.title")}</h2>
      <p className="mt-1 text-sm text-ink-muted">{t("admin.messages.subtitle")}</p>

      <div className="-mx-[18px] mt-3 flex gap-1.5 overflow-x-auto px-[18px] pb-1" role="tablist">
        {FILTERS.map((option) => (
          <button
            key={option}
            type="button"
            role="tab"
            aria-selected={filter === option}
            onClick={() => setFilter(option)}
            className={`whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-bold ${
              filter === option ? "border-primary bg-primary text-white" : "border-border bg-surface text-ink-muted"
            }`}
          >
            {option === "all" ? t("admin.messages.filterAll") : label("notificationStatus", option)}
          </button>
        ))}
      </div>

      <Button block className="mt-3" disabled={dispatch.isPending} onClick={() => dispatch.mutate()}>
        {dispatch.isPending ? t("admin.messages.dispatching") : t("admin.messages.dispatch")}
      </Button>
      {result && (
        <p className="mt-2 text-center text-xs text-ink-muted" aria-live="polite">
          {result}
        </p>
      )}

      {messages.isLoading ? (
        <Skeleton className="mt-3 h-32" />
      ) : items.length === 0 ? (
        <div className="mt-3">
          <EmptyState icon={Bell} title={t("admin.messages.empty")} description={t("admin.messages.emptyBody")} />
        </div>
      ) : (
        <ul className="mt-3 flex flex-col gap-2">
          {items.map((message) => (
            <li key={message.id}>
              <Card className="text-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-bold text-ink">{label("notificationTemplate", message.template)}</p>
                    <p className="mt-0.5 truncate text-xs text-ink-muted" dir="ltr">
                      {message.channel} · {message.recipient || "—"}
                    </p>
                  </div>
                  <Badge tone={TONES[message.status]}>{label("notificationStatus", message.status)}</Badge>
                </div>
                <p className="mt-1 whitespace-pre-line text-xs text-ink">{message.body.slice(0, 220)}</p>
                <p className="mt-1 text-[11px] text-ink-muted">
                  {message.sent_at
                    ? `${t("admin.messages.sent")}: ${formatDate(new Date(message.sent_at))} ${formatTime(new Date(message.sent_at))}`
                    : `${t("admin.messages.scheduled")}: ${formatDate(new Date(message.scheduled_for))} ${formatTime(new Date(message.scheduled_for))}`}
                  {message.attempts > 0 ? ` · ${t("admin.messages.attempts")}: ${message.attempts}` : ""}
                  {message.error ? ` · ${message.error}` : ""}
                </p>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
