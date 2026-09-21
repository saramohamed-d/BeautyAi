import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { holdSlot } from "@/services/availability-service";
import { useBookingContext } from "@/lib/booking-context";
import { ApiError } from "@/lib/api-client";
import type { Availability } from "@/types/availability";

export type CheckoutError = "taken" | "generic";

/**
 * Holds the chosen slot for the patient, then opens /payment. If someone
 * else got the slot first, reports "taken" and clears it from the draft
 * so the patient can pick another time.
 */
export function useStartCheckout() {
  const router = useRouter();
  const { setDraft } = useBookingContext();
  const queryClient = useQueryClient();
  const [isHolding, setIsHolding] = useState(false);
  const [error, setError] = useState<CheckoutError | null>(null);

  async function startCheckout(slot: Availability) {
    setIsHolding(true);
    setError(null);
    try {
      const hold = await holdSlot(slot.id);
      setDraft((prev) => ({ ...prev, heldUntil: hold.held_until }));
      router.push("/payment");
    } catch (err) {
      if (err instanceof ApiError && err.code === "slot_unavailable") {
        setDraft((prev) => ({ ...prev, slot: null, heldUntil: null }));
        // Refetch so the taken time disappears from the grid.
        queryClient.invalidateQueries({ queryKey: ["availability"] });
        queryClient.invalidateQueries({ queryKey: ["doctor-search"] });
        setError("taken");
      } else {
        setError("generic");
      }
    } finally {
      setIsHolding(false);
    }
  }

  return { startCheckout, isHolding, error, resetError: () => setError(null) };
}
