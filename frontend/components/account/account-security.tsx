"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { BadgeCheck, Download, ShieldAlert, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Notice } from "@/components/ui/notice";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import { ApiError } from "@/lib/api-client";
import {
  confirmVerification,
  deleteMyAccount,
  exportMyData,
  requestVerification,
} from "@/services/auth-service";
import type { AuthUser } from "@/types/auth";

/**
 * Confirming an email address, and the two data rights Egypt's PDPL
 * gives people: a copy of what we hold, and deletion (Sprint 17).
 */
export function AccountSecurity({ user }: { user: AuthUser }) {
  return (
    <>
      {user.email && !user.email_verified_at && <VerifyEmail />}
      <YourData />
      <DeleteAccount />
    </>
  );
}

function VerifyEmail() {
  const { t } = useI18n();
  const { refresh } = useAuth();
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = useMutation({
    mutationFn: () => requestVerification("email"),
    onSuccess: () => {
      setSent(true);
      setError(null);
    },
    onError: () => setError(t("errors.generic")),
  });
  const confirm = useMutation({
    mutationFn: () => confirmVerification(code.trim(), "email"),
    onSuccess: () => refresh(),
    onError: (err) =>
      setError(err instanceof ApiError && err.status === 401 ? t("verifyEmail.wrongCode") : t("errors.generic")),
  });

  return (
    <Card className="text-sm">
      <p className="flex items-center gap-2 font-bold text-ink">
        <BadgeCheck className="h-4 w-4 text-primary-dark" aria-hidden="true" />
        {t("verifyEmail.title")}
      </p>
      <p className="mt-1 text-xs text-ink-muted">{t("verifyEmail.subtitle")}</p>

      {sent ? (
        <div className="mt-2 flex items-end gap-2">
          <Input
            label={t("verifyEmail.code")}
            inputMode="numeric"
            dir="ltr"
            className="flex-1"
            value={code}
            onChange={(event) => setCode(event.target.value)}
          />
          <Button
            className="h-11 w-auto px-3 text-xs"
            disabled={code.trim().length < 4 || confirm.isPending}
            onClick={() => confirm.mutate()}
          >
            {confirm.isPending ? t("verifyEmail.checking") : t("verifyEmail.confirm")}
          </Button>
        </div>
      ) : (
        <Button variant="secondary" block className="mt-2" disabled={send.isPending} onClick={() => send.mutate()}>
          {send.isPending ? t("verifyEmail.sending") : t("verifyEmail.send")}
        </Button>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </Card>
  );
}

function YourData() {
  const { t } = useI18n();
  const [error, setError] = useState<string | null>(null);

  const download = useMutation({
    mutationFn: exportMyData,
    onSuccess: (data) => {
      // Straight to a file: the export is the person's own copy, and it
      // never needs to sit in the page.
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "beautyai-my-data.json";
      link.click();
      URL.revokeObjectURL(url);
    },
    onError: () => setError(t("errors.generic")),
  });

  return (
    <Card className="text-sm">
      <p className="flex items-center gap-2 font-bold text-ink">
        <Download className="h-4 w-4 text-primary-dark" aria-hidden="true" />
        {t("yourData.title")}
      </p>
      <p className="mt-1 text-xs text-ink-muted">{t("yourData.subtitle")}</p>
      <Button variant="secondary" block className="mt-2" disabled={download.isPending} onClick={() => download.mutate()}>
        {download.isPending ? t("yourData.preparing") : t("yourData.download")}
      </Button>
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </Card>
  );
}

function DeleteAccount() {
  const { t } = useI18n();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const remove = useMutation({
    mutationFn: () => deleteMyAccount(password),
    onSuccess: () => {
      // The session died with the account; start again as a visitor.
      window.location.href = "/";
    },
    onError: (err) =>
      setError(err instanceof ApiError && err.status === 401 ? t("deleteAccount.wrongPassword") : t("errors.generic")),
  });

  return (
    <Card className="text-sm">
      <p className="flex items-center gap-2 font-bold text-ink">
        <ShieldAlert className="h-4 w-4 text-primary-dark" aria-hidden="true" />
        {t("deleteAccount.title")}
      </p>
      <p className="mt-1 text-xs text-ink-muted">{t("deleteAccount.subtitle")}</p>

      {open ? (
        <>
          <Notice className="mt-2 text-xs">{t("deleteAccount.whatHappens")}</Notice>
          <Input
            label={t("deleteAccount.confirmPassword")}
            type="password"
            dir="ltr"
            className="mt-2"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          {error && (
            <p role="alert" className="mt-2 text-sm text-red-700">
              {error}
            </p>
          )}
          <div className="mt-2 flex gap-2">
            <Button
              className="h-10 flex-1 text-xs"
              disabled={!password || remove.isPending}
              onClick={() => remove.mutate()}
            >
              <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
              {remove.isPending ? t("deleteAccount.deleting") : t("deleteAccount.confirm")}
            </Button>
            <Button variant="secondary" className="h-10 flex-1 text-xs" onClick={() => setOpen(false)}>
              {t("clinic.cancel")}
            </Button>
          </div>
        </>
      ) : (
        <Button variant="secondary" block className="mt-2" onClick={() => setOpen(true)}>
          {t("deleteAccount.start")}
        </Button>
      )}
    </Card>
  );
}
