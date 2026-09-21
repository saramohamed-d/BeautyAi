"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserRound } from "lucide-react";
import { AdminShell } from "@/components/admin/admin-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useI18n } from "@/lib/i18n/provider";
import { ApiError } from "@/lib/api-client";
import { LIVE } from "@/lib/query-options";
import { useDebounced } from "@/hooks/use-debounced";
import { fetchUsers, setUserStatus } from "@/services/admin-service";
import type { AdminUser } from "@/types/admin";
import type { UserRole, UserStatus } from "@/types/auth";

const ROLES: (UserRole | "all")[] = ["all", "patient", "doctor", "clinic_admin", "platform_admin"];
const STATUSES: (UserStatus | "all")[] = ["all", "active", "suspended", "pending"];

/** Every login on the platform, with suspend and restore (Sprint 14). */
export default function AdminUsersPage() {
  return <AdminShell>{() => <Users />}</AdminShell>;
}

function Users() {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const [role, setRole] = useState<UserRole | "all">("all");
  const [status, setStatus] = useState<UserStatus | "all">("all");
  const q = useDebounced(search, 300);

  const users = useQuery({
    queryKey: ["admin-users", { q, role, status }],
    queryFn: () =>
      fetchUsers({
        page_size: 100,
        ...(q ? { q } : {}),
        ...(role === "all" ? {} : { role }),
        ...(status === "all" ? {} : { status }),
      }),
    ...LIVE,
  });

  const items = users.data?.items ?? [];

  return (
    <>
      <h2 className="text-lg font-bold text-ink">{t("admin.users.title")}</h2>
      <p className="mt-1 text-sm text-ink-muted">{t("admin.users.subtitle")}</p>

      <Card className="mt-3 flex flex-col gap-3">
        <Input
          label={t("admin.users.search")}
          dir="ltr"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <div className="flex gap-2">
          <label className="flex flex-1 flex-col gap-1 text-sm">
            <span className="font-semibold text-ink-muted">{t("admin.users.filterRole")}</span>
            <select
              className="h-11 rounded-card border border-border bg-surface px-3 text-sm text-ink"
              value={role}
              onChange={(event) => setRole(event.target.value as UserRole | "all")}
            >
              {ROLES.map((option) => (
                <option key={option} value={option}>
                  {option === "all" ? t("admin.users.all") : t(`roles.${option}` as never)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-1 flex-col gap-1 text-sm">
            <span className="font-semibold text-ink-muted">{t("admin.users.filterStatus")}</span>
            <select
              className="h-11 rounded-card border border-border bg-surface px-3 text-sm text-ink"
              value={status}
              onChange={(event) => setStatus(event.target.value as UserStatus | "all")}
            >
              {STATUSES.map((option) => (
                <option key={option} value={option}>
                  {option === "all" ? t("admin.users.all") : option}
                </option>
              ))}
            </select>
          </label>
        </div>
      </Card>

      {users.isLoading ? (
        <Skeleton className="mt-3 h-32" />
      ) : items.length === 0 ? (
        <div className="mt-3">
          <EmptyState icon={UserRound} title={t("admin.users.empty")} description={t("admin.users.emptyBody")} />
        </div>
      ) : (
        <ul className="mt-3 flex flex-col gap-2">
          {items.map((user) => (
            <li key={user.id}>
              <UserRow user={user} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function UserRow({ user }: { user: AdminUser }) {
  const { t, formatDate } = useI18n();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const suspended = user.status === "suspended";

  const change = useMutation({
    mutationFn: (next: UserStatus) =>
      setUserStatus(user.id, next, next === "suspended" ? window.prompt(t("admin.users.suspendReason")) || undefined : undefined),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
    },
    onError: (err) =>
      setError(
        err instanceof ApiError && err.code === "cannot_suspend_self"
          ? t("admin.users.cannotSuspendSelf")
          : t("errors.generic")
      ),
  });

  return (
    <Card className="text-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-bold text-ink">{user.full_name ?? user.email ?? user.phone}</p>
          <p className="mt-0.5 truncate text-xs text-ink-muted" dir="ltr">
            {user.email ?? user.phone}
          </p>
          <p className="mt-0.5 text-xs text-ink-muted">
            {t(`roles.${user.role}` as never)} · {t("admin.users.lastLogin")}:{" "}
            {user.last_login_at ? formatDate(new Date(user.last_login_at), "long") : t("admin.users.never")}
          </p>
        </div>
        <Badge tone={suspended ? "neutral" : "sage"}>{user.status}</Badge>
      </div>
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}
      <Button
        variant="secondary"
        className="mt-2 h-9 w-auto px-3 text-xs"
        disabled={change.isPending}
        onClick={() => {
          if (suspended) {
            change.mutate("active");
            return;
          }
          if (window.confirm(t("admin.users.suspendConfirm"))) change.mutate("suspended");
        }}
      >
        {suspended ? t("admin.users.restore") : t("admin.users.suspend")}
      </Button>
    </Card>
  );
}
