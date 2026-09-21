"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n/provider";
import { updatePatient } from "@/services/patient-service";
import type { Patient } from "@/types/patient";
import type { MessageKey } from "@/lib/i18n/types";

type Channel = "notify_email" | "notify_sms" | "notify_whatsapp";

const CHANNELS: { key: Channel; label: MessageKey; hint: MessageKey }[] = [
  { key: "notify_email", label: "notifications.email", hint: "notifications.emailHint" },
  { key: "notify_sms", label: "notifications.sms", hint: "notifications.smsHint" },
  { key: "notify_whatsapp", label: "notifications.whatsapp", hint: "notifications.whatsappHint" },
];

/**
 * Which messages a patient wants (Sprint 15). Appointment reminders,
 * receipts and the aftercare follow-up go out on the channels left on
 * here; turning them all off means only what they see in the app.
 */
export function NotificationPreferences({ patient }: { patient: Patient }) {
  const { t } = useI18n();
  const { refresh } = useAuth();
  const [values, setValues] = useState({
    notify_email: patient.notify_email,
    notify_sms: patient.notify_sms,
    notify_whatsapp: patient.notify_whatsapp,
  });
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (patch: Partial<Record<Channel, boolean>>) => updatePatient(patient.id, patch),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: () => setError(t("errors.generic")),
  });

  function toggle(key: Channel) {
    const next = { ...values, [key]: !values[key] };
    setValues(next);
    save.mutate({ [key]: next[key] });
  }

  return (
    <Card className="text-sm">
      <p className="flex items-center gap-2 font-bold text-ink">
        <Bell className="h-4 w-4 text-primary-dark" aria-hidden="true" />
        {t("notifications.title")}
      </p>
      <p className="mt-1 text-xs text-ink-muted">{t("notifications.subtitle")}</p>

      <ul className="mt-2 flex flex-col gap-2">
        {CHANNELS.map(({ key, label, hint }) => (
          <li key={key}>
            <label className="flex items-start gap-2.5">
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 accent-[color:var(--color-primary,#b34a63)]"
                checked={values[key]}
                onChange={() => toggle(key)}
              />
              <span>
                <span className="font-semibold text-ink">{t(label)}</span>
                <span className="block text-xs text-ink-muted">{t(hint)}</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </Card>
  );
}
