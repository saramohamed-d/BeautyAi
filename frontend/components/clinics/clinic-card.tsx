import Link from "next/link";
import { MapPin, Building2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { Clinic } from "@/types/clinic";

export function ClinicCard({ clinic }: { clinic: Clinic }) {
  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-gold-soft text-ink">
          <Building2 className="h-5 w-5" strokeWidth={1.75} />
        </div>
        <div>
          <p className="font-semibold text-ink">{clinic.name}</p>
          <p className="flex items-center gap-1 text-sm text-ink-muted">
            <MapPin className="h-3.5 w-3.5" />
            {clinic.city}، {clinic.country}
          </p>
        </div>
      </div>

      {clinic.description && <p className="line-clamp-2 text-sm text-ink-muted">{clinic.description}</p>}

      <div className="flex justify-end">
        <Link href={`/clinics/${clinic.id}`}>
          <Button variant="secondary" size="sm">عرض العيادة</Button>
        </Link>
      </div>
    </Card>
  );
}
