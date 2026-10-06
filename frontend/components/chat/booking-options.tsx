"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarDays, MapPin, Star } from "lucide-react";
import { DoctorAvatar } from "@/components/doctors/doctor-avatar";
import { Button } from "@/components/ui/button";
import { useChatActions } from "@/components/chat/chat-actions";
import { useBookingContext } from "@/lib/booking-context";
import { useI18n } from "@/lib/i18n/provider";
import { ApiError } from "@/lib/api-client";
import { reserveBookingOption } from "@/services/chat-service";
import type { BookingOffer } from "@/types/chat";

/**
 * The booking agent's options. Tapping Reserve holds the time (only
 * options the agent offered are accepted) and opens payment, where the
 * patient confirms. Nothing is booked from here.
 */
export function BookingOptions({ offer, conversationId }: { offer: BookingOffer; conversationId: string }) {
  const { t, label, formatDate, formatTime, formatNumber, formatCurrency } = useI18n();
  const router = useRouter();
  const chat = useChatActions();
  const { setDraft } = useBookingContext();
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<"taken" | "failed" | null>(null);

  async function reserve(availabilityId: string) {
    setPending(availabilityId);
    setError(null);
    try {
      const r = await reserveBookingOption(conversationId, availabilityId);
      setDraft(() => ({ doctor: r.doctor, clinic: r.clinic, procedure: null, slot: r.slot, notes: "", heldUntil: r.hold.held_until }));
      router.push("/payment");
    } catch (err) {
      setError(err instanceof ApiError && err.code === "slot_unavailable" ? "taken" : "failed");
      setPending(null);
    }
  }

  if (offer.options.length === 0) return null;

  return (
    <div className="flex w-full flex-col gap-2">
      {offer.options.map((option) => {
        const start = new Date(option.start_time);
        return (
          <div key={option.availability_id} className="rounded-card border border-border bg-surface p-3">
            <div className="flex items-start gap-[11px]">
              <DoctorAvatar avatar={option.doctor.avatar} />
              <div className="min-w-0 flex-1 text-xs text-ink-muted">
                <p dir="auto" className="text-sm font-bold text-ink">{option.doctor.full_name}</p>
                <p className="mt-0.5 flex items-center gap-1">
                  {label("specialties", option.doctor.specialty)}
                  {option.doctor.rating != null && (
                    <>
                      {" · "}
                      <Star className="h-3 w-3 fill-gold-star text-gold-star" aria-hidden="true" />
                      <span className="font-semibold text-gold">{formatNumber(option.doctor.rating, 1)}</span>
                    </>
                  )}
                </p>
                <p dir="auto" className="mt-1 flex items-center gap-1.5">
                  <MapPin className="h-3.5 w-3.5 shrink-0" /> {option.clinic.name} · {option.clinic.city}
                </p>
                <p className="mt-0.5 flex items-center gap-1.5 font-semibold text-ink">
                  <CalendarDays className="h-3.5 w-3.5 shrink-0 text-primary-dark" /> {formatDate(start, "long")} · {formatTime(start)}
                </p>
                {option.consultation_fee != null && <p className="mt-0.5">{t("payment.fee")}: {formatCurrency(option.consultation_fee)}</p>}
              </div>
            </div>
            <Button size="sm" block className="mt-2.5" disabled={pending !== null} onClick={() => reserve(option.availability_id)}>
              {pending === option.availability_id ? t("booking.holding") : t("chat.reserve")}
            </Button>
          </div>
        );
      })}
      {error && (
        <div role="alert" className="rounded-card bg-primary-soft p-3 text-sm text-primary-dark">
          <p>{error === "taken" ? t("booking.taken") : t("errors.generic")}</p>
          {chat && error === "taken" && (
            <Button size="sm" variant="secondary" className="mt-2" onClick={() => chat.send(t("chat.showOtherTimes"))}>
              {t("chat.showOtherTimesButton")}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
