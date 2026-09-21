"use client";

import Link from "next/link";
import { Building2, MapPin } from "lucide-react";
import type { Clinic } from "@/types/clinic";

export function ClinicCard({ clinic }: { clinic: Clinic }) {
  return (
    <Link
      href={`/clinics/${clinic.id}`}
      className="flex items-center gap-[11px] rounded-card border border-border bg-surface p-3 transition-colors hover:border-primary-line"
    >
      <div className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-sage-soft text-sage">
        <Building2 className="h-5 w-5" strokeWidth={1.75} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-bold text-ink">{clinic.name}</p>
        <p className="mt-0.5 flex items-center gap-1 truncate text-xs text-ink-muted">
          <MapPin className="h-3 w-3 shrink-0" />
          {clinic.address ? `${clinic.address} · ` : ""}
          {clinic.city}
        </p>
        {clinic.description && <p className="mt-1 line-clamp-1 text-xs text-ink-muted">{clinic.description}</p>}
      </div>
    </Link>
  );
}
