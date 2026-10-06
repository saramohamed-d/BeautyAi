import { cn } from "@/lib/utils";

/**
 * Illustrated doctor avatars. Each doctor picks one (stored as
 * `doctors.avatar`, e.g. "woman-2"); doctors who haven't picked yet get
 * the neutral one. Drawn here as inline SVG: no stock photos, nothing to
 * download, and they match the pink theme.
 */
export const AVATAR_KEYS = ["woman-1", "woman-2", "woman-3", "woman-4", "woman-5", "man-1", "man-2", "man-3"] as const;
export type AvatarKey = (typeof AVATAR_KEYS)[number];

type Hair = "long" | "bob" | "bun" | "hijab" | "short" | "beard";

interface Look {
  bg: string;
  skin: string;
  hair: string;
  style: Hair;
}

const LOOKS: Record<AvatarKey, Look> = {
  "woman-1": { bg: "#FCE4EC", skin: "#F4C9A8", hair: "#3B2620", style: "long" },
  "woman-2": { bg: "#F1E9F7", skin: "#E7B48F", hair: "#6B3F2A", style: "bob" },
  "woman-3": { bg: "#FDECF1", skin: "#F1C3A0", hair: "#C8577D", style: "hijab" },
  "woman-4": { bg: "#E9F1F3", skin: "#C98E6A", hair: "#7A6A8F", style: "hijab" },
  "woman-5": { bg: "#FFF1E6", skin: "#F6D2B6", hair: "#2A1F2D", style: "bun" },
  "man-1": { bg: "#E9F1F3", skin: "#E3AE88", hair: "#2A1F2D", style: "short" },
  "man-2": { bg: "#F1E9F7", skin: "#C98E6A", hair: "#3B2620", style: "beard" },
  "man-3": { bg: "#FCE4EC", skin: "#F4C9A8", hair: "#6B3F2A", style: "short" },
};

export function isAvatarKey(value: string | null | undefined): value is AvatarKey {
  return Boolean(value) && (AVATAR_KEYS as readonly string[]).includes(value as string);
}

function HairBack({ look }: { look: Look }) {
  switch (look.style) {
    case "long":
      return <path d="M19 31c-2-12 4-20 13-20s15 8 13 20l2 17H17z" fill={look.hair} />;
    case "bob":
      return <path d="M19 32c-1-11 5-19 13-19s14 8 13 19l-1 7H20z" fill={look.hair} />;
    case "bun":
      return <circle cx="32" cy="11" r="5.5" fill={look.hair} />;
    case "hijab":
      return <path d="M16.5 36c-1.5-15 6-24 15.5-24s17 9 15.5 24c-.5 6-3.5 10-7.5 12H24c-4-2-7-6-7.5-12z" fill={look.hair} />;
    default:
      return null;
  }
}

function HairFront({ look }: { look: Look }) {
  switch (look.style) {
    case "long":
    case "bob":
      return <path d="M20.5 27c1-8 6-12.5 11.5-12.5S42.5 19 43.5 27c-4.5-2.5-8.5-5-11.5-8.5-3 3.5-7 6-11.5 8.5z" fill={look.hair} />;
    case "bun":
      return <path d="M20.5 26.5c0-8.5 5-13.5 11.5-13.5S43.5 18 43.5 26.5C40.5 22.5 36.5 20.5 32 20.5s-8.5 2-11.5 6z" fill={look.hair} />;
    case "hijab":
      return <path d="M21 23.5c2-6.5 6-9.5 11-9.5s9 3 11 9.5" stroke="#FFFFFF" strokeOpacity=".35" strokeWidth="1.5" fill="none" />;
    case "short":
    case "beard":
      return <path d="M20.5 26c0-9 5-14 11.5-14s11.5 5 11.5 14c-2-3-5-5-8-5.5-5-.5-9.5 1.5-15 5.5z" fill={look.hair} />;
  }
}

function Illustration({ look }: { look: Look }) {
  return (
    <svg viewBox="0 0 64 64" className="h-full w-full" aria-hidden="true">
      <rect width="64" height="64" fill={look.bg} />
      <HairBack look={look} />
      {/* White coat with a pink scrub neckline and stethoscope. */}
      <path d="M9 64c0-11.5 9.5-18.5 23-18.5S55 52.5 55 64z" fill="#FFFFFF" />
      <path d="M26.5 46l5.5 7 5.5-7" fill="#F06A95" />
      <rect x="28" y="36" width="8" height="10" rx="3" fill={look.skin} />
      <path d="M23.5 48.5v5a4.2 4.2 0 0 0 8.4 0" stroke="#B0255A" strokeWidth="1.3" fill="none" strokeLinecap="round" />
      <circle cx="40" cy="55" r="1.8" fill="#B0255A" />
      <ellipse cx="32" cy="28.5" rx={look.style === "hijab" ? 10 : 11} ry="12.5" fill={look.skin} />
      <HairFront look={look} />
      {look.style === "beard" && <path d="M21.5 30c.8 7.5 5 11.5 10.5 11.5s9.7-4 10.5-11.5c-2 3-5 4.3-10.5 4.3S23.5 33 21.5 30z" fill={look.hair} />}
      <circle cx="28" cy="29" r="1.15" fill="#2A1F2D" />
      <circle cx="36" cy="29" r="1.15" fill="#2A1F2D" />
      <circle cx="25.5" cy="32.5" r="2" fill="#F06A95" opacity=".25" />
      <circle cx="38.5" cy="32.5" r="2" fill="#F06A95" opacity=".25" />
      <path d="M29.3 34.3c1.6 1.3 3.8 1.3 5.4 0" stroke="#9C4A55" strokeWidth="1.1" fill="none" strokeLinecap="round" />
    </svg>
  );
}

function NeutralIllustration() {
  return (
    <svg viewBox="0 0 64 64" className="h-full w-full" aria-hidden="true">
      <rect width="64" height="64" fill="#FDECF1" />
      <circle cx="32" cy="26" r="11" fill="#F6B8CB" />
      <path d="M10 64c0-11.5 9.5-18.5 22-18.5S54 52.5 54 64z" fill="#FFFFFF" />
      <path d="M26.5 46l5.5 7 5.5-7" fill="#F6B8CB" />
      <path d="M23.5 48.5v5a4.2 4.2 0 0 0 8.4 0" stroke="#D6336C" strokeWidth="1.3" fill="none" strokeLinecap="round" />
      <circle cx="40" cy="55" r="1.8" fill="#D6336C" />
    </svg>
  );
}

const sizes = {
  sm: "h-10 w-10",
  md: "h-14 w-14",
  lg: "h-20 w-20",
  xl: "h-28 w-28",
};

export function DoctorAvatar({
  avatar,
  size = "md",
  className,
}: {
  avatar: string | null | undefined;
  size?: keyof typeof sizes;
  className?: string;
}) {
  return (
    <div className={cn("shrink-0 overflow-hidden rounded-full ring-2 ring-white", sizes[size], className)}>
      {isAvatarKey(avatar) ? <Illustration look={LOOKS[avatar]} /> : <NeutralIllustration />}
    </div>
  );
}
