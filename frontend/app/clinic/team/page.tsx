"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, UserRound } from "lucide-react";
import { ClinicShell } from "@/components/clinic/clinic-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useI18n } from "@/lib/i18n/provider";
import { ApiError } from "@/lib/api-client";
import { useDoctors } from "@/hooks/use-doctors";
import {
  addClinicStaff,
  fetchClinicStaff,
  removeClinicStaff,
  updateClinicStaff,
} from "@/services/clinic-service";
import type { ClinicStaffMember } from "@/types/clinic";

/** The clinic's doctors and their consultation fee here (Sprint 13). */
export default function ClinicTeamPage() {
  const { t } = useI18n();
  return <ClinicShell title={t("clinic.title")}>{(clinic) => <Team clinicId={clinic.id} />}</ClinicShell>;
}

function Team({ clinicId }: { clinicId: string }) {
  const { t, formatCurrency } = useI18n();
  const queryClient = useQueryClient();
  const [doctorId, setDoctorId] = useState("");
  const [fee, setFee] = useState("");
  const [error, setError] = useState<string | null>(null);

  const staff = useQuery({ queryKey: ["clinic-staff", clinicId], queryFn: () => fetchClinicStaff(clinicId) });
  const { data: doctorsData } = useDoctors({ page_size: 100 });
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["clinic-staff", clinicId] });
    queryClient.invalidateQueries({ queryKey: ["clinic-summary", clinicId] });
  };

  const add = useMutation({
    mutationFn: () =>
      addClinicStaff(clinicId, {
        role: "doctor",
        doctor_id: doctorId,
        consultation_fee: fee === "" ? null : Number(fee),
      }),
    onSuccess: () => {
      setDoctorId("");
      setFee("");
      invalidate();
    },
    onError: (err) =>
      setError(err instanceof ApiError && err.status === 409 ? t("clinic.team.alreadyAdded") : t("errors.generic")),
  });
  const remove = useMutation({
    mutationFn: (staffId: string) => removeClinicStaff(clinicId, staffId),
    onSuccess: invalidate,
  });

  const doctors = staff.data?.filter((member) => member.role === "doctor") ?? [];
  const onTeam = new Set(doctors.map((member) => member.doctor_id));
  const addable = (doctorsData?.items ?? []).filter((doctor) => !onTeam.has(doctor.id));

  return (
    <>
      <h2 className="text-lg font-bold text-ink">{t("clinic.team.title")}</h2>
      <p className="mt-1 text-sm text-ink-muted">{t("clinic.team.subtitle")}</p>

      <Card className="mt-3 flex flex-col gap-3">
        <p className="text-sm font-bold text-ink">{t("clinic.team.addDoctor")}</p>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-semibold text-ink-muted">{t("clinic.team.chooseDoctor")}</span>
          <select
            className="h-11 rounded-card border border-border bg-surface px-3 text-sm text-ink"
            value={doctorId}
            onChange={(event) => setDoctorId(event.target.value)}
          >
            <option value="">—</option>
            {addable.map((doctor) => (
              <option key={doctor.id} value={doctor.id}>
                {doctor.full_name} · {doctor.specialty}
              </option>
            ))}
          </select>
        </label>
        <Input
          label={t("clinic.team.fee")}
          type="number"
          inputMode="decimal"
          min={0}
          value={fee}
          onChange={(event) => setFee(event.target.value)}
        />
        <p className="-mt-1 text-xs text-ink-muted">{t("clinic.team.feeHelp")}</p>
        {addable.length === 0 && <p className="text-xs text-ink-muted">{t("clinic.team.noneAvailable")}</p>}
        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}
        <Button block disabled={!doctorId || add.isPending} onClick={() => add.mutate()}>
          {add.isPending ? t("clinic.team.adding") : t("clinic.team.add")}
        </Button>
      </Card>

      {staff.isLoading ? (
        <Skeleton className="mt-3 h-32" />
      ) : doctors.length === 0 ? (
        <div className="mt-3">
          <EmptyState icon={UserRound} title={t("clinic.team.empty")} description={t("clinic.team.emptyBody")} />
        </div>
      ) : (
        <ul className="mt-3 flex flex-col gap-2">
          {doctors.map((member) => (
            <li key={member.id}>
              <MemberRow
                clinicId={clinicId}
                member={member}
                onRemoved={() => remove.mutate(member.id)}
                formatCurrency={formatCurrency}
              />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function MemberRow({
  clinicId,
  member,
  onRemoved,
  formatCurrency,
}: {
  clinicId: string;
  member: ClinicStaffMember;
  onRemoved: () => void;
  formatCurrency: (value: string | number | null | undefined) => string;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [fee, setFee] = useState(member.consultation_fee ?? "");
  const save = useMutation({
    mutationFn: () =>
      updateClinicStaff(clinicId, member.id, { consultation_fee: fee === "" ? null : Number(fee) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["clinic-staff", clinicId] }),
  });
  const changed = String(fee) !== String(member.consultation_fee ?? "");

  return (
    <Card className="text-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-bold text-ink">{member.full_name}</p>
          <p className="mt-0.5 text-xs text-ink-muted">{member.specialty}</p>
          {member.verification_status !== "verified" && (
            <Badge tone="neutral" className="mt-1">
              {t("clinic.team.notVerifiedYet")}
            </Badge>
          )}
        </div>
        <button
          type="button"
          aria-label={t("clinic.remove")}
          className="text-ink-muted hover:text-red-700"
          onClick={() => {
            if (window.confirm(t("clinic.confirmRemove"))) onRemoved();
          }}
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      <div className="mt-2 flex items-end gap-2">
        <Input
          label={t("clinic.team.fee")}
          type="number"
          inputMode="decimal"
          min={0}
          className="flex-1"
          value={fee}
          onChange={(event) => setFee(event.target.value)}
        />
        <Button
          variant="secondary"
          className="h-11 w-auto px-3 text-xs"
          disabled={!changed || save.isPending}
          onClick={() => save.mutate()}
        >
          {save.isPending ? t("clinic.saving") : t("clinic.team.saveFee")}
        </Button>
      </div>
      <p className="mt-1 text-xs text-ink-muted">
        {member.consultation_fee ? formatCurrency(member.consultation_fee) : t("clinic.team.feeNotSet")}
      </p>
    </Card>
  );
}
