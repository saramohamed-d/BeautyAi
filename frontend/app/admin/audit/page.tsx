"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ScrollText } from "lucide-react";
import { AdminShell } from "@/components/admin/admin-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useI18n } from "@/lib/i18n/provider";
import { LIVE } from "@/lib/query-options";
import { useDebounced } from "@/hooks/use-debounced";
import { fetchAuditEvents } from "@/services/admin-service";

const RESOURCES = ["", "doctor", "user", "payment"];
// The log grows forever; show a screenful and let the admin ask for more.
const PAGE = 25;

/** The append-only record of administrator decisions (Sprint 14). */
export default function AdminAuditPage() {
  return <AdminShell>{() => <AuditLog />}</AdminShell>;
}

function AuditLog() {
  const { t, formatDate, formatTime } = useI18n();
  const [action, setAction] = useState("");
  const [resource, setResource] = useState("");
  const [shown, setShown] = useState(PAGE);
  const query = useDebounced(action, 300);

  const events = useQuery({
    queryKey: ["admin-audit", { query, resource, shown }],
    queryFn: () =>
      fetchAuditEvents({
        page_size: shown,
        ...(query ? { action: query } : {}),
        ...(resource ? { resource_type: resource } : {}),
      }),
    ...LIVE,
  });

  const items = events.data?.items ?? [];

  return (
    <>
      <h2 className="text-lg font-bold text-ink">{t("admin.audit.title")}</h2>
      <p className="mt-1 text-sm text-ink-muted">{t("admin.audit.subtitle")}</p>

      <Card className="mt-3 flex gap-2">
        <Input
          label={t("admin.audit.filterAction")}
          dir="ltr"
          className="flex-1"
          placeholder="doctor."
          value={action}
          onChange={(event) => {
            setShown(PAGE);
            setAction(event.target.value);
          }}
        />
        <label className="flex flex-1 flex-col gap-1 text-sm">
          <span className="font-semibold text-ink-muted">{t("admin.audit.filterResource")}</span>
          <select
            className="h-11 rounded-card border border-border bg-surface px-3 text-sm text-ink"
            value={resource}
            onChange={(event) => {
              setShown(PAGE);
              setResource(event.target.value);
            }}
          >
            {RESOURCES.map((option) => (
              <option key={option} value={option}>
                {option || t("admin.users.all")}
              </option>
            ))}
          </select>
        </label>
      </Card>

      {events.isLoading ? (
        <Skeleton className="mt-3 h-32" />
      ) : items.length === 0 ? (
        <div className="mt-3">
          <EmptyState icon={ScrollText} title={t("admin.audit.empty")} description={t("admin.audit.emptyBody")} />
        </div>
      ) : (
        <ul className="mt-3 flex flex-col gap-1.5">
          {items.map((event) => (
            <li key={event.id}>
              <Card className="text-sm">
                <div className="flex items-start justify-between gap-3">
                  <p className="font-bold text-ink" dir="ltr">
                    {event.action}
                  </p>
                  <span className="shrink-0 text-xs text-ink-muted">
                    {formatDate(new Date(event.created_at))} · {formatTime(new Date(event.created_at))}
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-ink-muted">
                  {t("admin.audit.by")}{" "}
                  {event.actor_type === "system" ? t("admin.audit.system") : t(`roles.${event.actor_type}` as never)}
                  {" · "}
                  <span dir="ltr">
                    {event.resource_type}
                    {event.resource_id ? ` ${event.resource_id.slice(0, 8)}` : ""}
                  </span>
                </p>
                {event.extra_data && Object.keys(event.extra_data).length > 0 && (
                  <p className="mt-1 text-xs text-ink">
                    {Object.entries(event.extra_data)
                      .filter(([, value]) => value !== null && value !== "")
                      .map(([key, value]) => `${key}: ${String(value)}`)
                      .join(" · ")}
                  </p>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}

      {(events.data?.total ?? 0) > items.length && (
        <Button variant="secondary" block className="mt-3" onClick={() => setShown((count) => count + PAGE)}>
          {t("admin.audit.loadMore", { shown: items.length, total: events.data?.total ?? 0 })}
        </Button>
      )}
    </>
  );
}
