import Link from "next/link";
import { ShieldCheck, Star, Stethoscope } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Doctor } from "@/types/doctor";

export function DoctorCard({ doctor }: { doctor: Doctor }) {
  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary-dark">
            <Stethoscope className="h-5 w-5" strokeWidth={1.75} />
          </div>
          <div>
            <p className="font-semibold text-ink">{doctor.full_name}</p>
            <p className="text-sm text-ink-muted">{doctor.specialty}</p>
          </div>
        </div>
        {doctor.verification_status === "verified" && (
          <Badge tone="sage">
            <ShieldCheck className="h-3.5 w-3.5" />
            موثّق
          </Badge>
        )}
      </div>

      {doctor.bio && <p className="line-clamp-2 text-sm text-ink-muted">{doctor.bio}</p>}

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 text-sm text-ink-muted">
          {doctor.rating != null && (
            <span className="flex items-center gap-1 text-gold">
              <Star className="h-4 w-4 fill-gold text-gold" />
              <span className="text-ink">{Number(doctor.rating).toFixed(1)}</span>
            </span>
          )}
          {doctor.years_experience != null && <span>{doctor.years_experience} سنوات خبرة</span>}
        </div>
        <Link href={`/doctors/${doctor.id}`}>
          <Button variant="secondary" size="sm">عرض التفاصيل</Button>
        </Link>
      </div>
    </Card>
  );
}
