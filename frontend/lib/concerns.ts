import { CircleDot, Droplets, Flame, Hourglass, Palette, Sprout, type LucideIcon } from "lucide-react";

/**
 * Concern topics offered as quick starts for the AI consultation.
 *
 * Since Sprint 9 the specialty comes from the AI consultation's
 * assessment (backend: app/workflows/consultation.py), not from a fixed
 * lookup here. `id` values match the backend's concern categories.
 */
export const CONCERNS = [
  { id: "acne", icon: CircleDot },
  { id: "pigmentation", icon: Palette },
  { id: "hair_loss", icon: Sprout },
  { id: "anti_aging", icon: Hourglass },
  { id: "redness", icon: Flame },
  { id: "dark_spots", icon: Droplets },
] as const satisfies readonly { id: string; icon: LucideIcon }[];

export type ConcernId = (typeof CONCERNS)[number]["id"];

export function isConcernId(value: string | null | undefined): value is ConcernId {
  return CONCERNS.some((c) => c.id === value);
}
