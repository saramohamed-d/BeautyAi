"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Stethoscope, Trash2 } from "lucide-react";
import { ClinicShell } from "@/components/clinic/clinic-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useI18n } from "@/lib/i18n/provider";
import { ApiError } from "@/lib/api-client";
import { useProcedures } from "@/hooks/use-procedures";
import {
  addClinicService,
  fetchClinicServices,
  fetchClinicStaff,
  removeClinicService,
  updateClinicService,
} from "@/services/clinic-service";
import type { ClinicService } from "@/types/clinic";

/** What each doctor offers at this clinic, and for how much (Sprint 13). */
export default function ClinicServicesPage() {
  const { t } = useI18n();
  return <ClinicShell title={t("clinic.title")}>{(clinic) => <Services clinicId={clinic.id} />}</ClinicShell>;
}

function Services({ clinicId }: { clinicId: string }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [doctorId, setDoctorId] = useState("");
  const [procedureId, setProcedureId] = useState("");
  const [price, setPrice] = useState("");
  const [error, setError] = useState<string | null>(null);

  const services = useQuery({ queryKey: ["clinic-services", clinicId], queryFn: () => fetchClinicServices(clinicId) });
  const staff = useQuery({ queryKey: ["clinic-staff", clinicId], queryFn: () => fetchClinicStaff(clinicId) });
  const { data: proceduresData } = useProcedures({ page_size: 100 });
  const doctors = (staff.data ?? []).filter((member) => member.role === "doctor" && member.doctor_id);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["clinic-services", clinicId] });
    queryClient.invalidateQueries({ queryKey: ["clinic-summary", clinicId] });
  };

  const add = useMutation({
    mutationFn: () =>
      addClinicService(clinicId, { doctor_id: doctorId, procedure_id: procedureId, price: Number(price) }),
    onSuccess: () => {
      setProcedureId("");
      setPrice("");
      setError(null);
      invalidate();
    },
    onError: (err) =>
      setError(err instanceof ApiError && err.status === 409 ? t("clinic.services.duplicate") : t("errors.generic")),
  });
  const remove = useMutation({
    mutationFn: (serviceId: string) => removeClinicService(clinicId, serviceId),
    onSuccess: invalidate,
  });

  return (
    <>
      <h2 className="text-lg font-bold text-ink">{t("clinic.services.title")}</h2>
      <p className="mt-1 text-sm text-ink-muted">{t("clinic.services.subtitle")}</p>

      <Card className="mt-3 flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-semibold text-ink-muted">{t("clinic.services.doctor")}</span>
          <select
            className="h-11 rounded-card border border-border bg-surface px-3 text-sm text-ink"
            value={doctorId}
            onChange={(event) => setDoctorId(event.target.value)}
          >
            <option value="">—</option>
            {doctors.map((member) => (
              <option key={member.id} value={member.doctor_id ?? ""}>
                {member.full_name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-semibold text-ink-muted">{t("clinic.services.procedure")}</span>
          <select
            className="h-11 rounded-card border border-border bg-surface px-3 text-sm text-ink"
            value={procedureId}
            onChange={(event) => setProcedureId(event.target.value)}
          >
            <option value="">—</option>
            {(proceduresData?.items ?? []).map((procedure) => (
              <option key={procedure.id} value={procedure.id}>
                {procedure.name}
              </option>
            ))}
          </select>
        </label>
        <Input
          label={t("clinic.services.price")}
          type="number"
          inputMode="decimal"
          min={0}
          value={price}
          onChange={(event) => setPrice(event.target.value)}
        />
        {doctors.length === 0 && <p className="text-xs text-ink-muted">{t("clinic.services.needsTeam")}</p>}
        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}
        <Button block disabled={!doctorId || !procedureId || price === "" || add.isPending} onClick={() => add.mutate()}>
          {add.isPending ? t("clinic.services.adding") : t("clinic.services.add")}
        </Button>
      </Card>

      {services.isLoading ? (
        <Skeleton className="mt-3 h-32" />
      ) : (services.data ?? []).length === 0 ? (
        <div className="mt-3">
          <EmptyState
            icon={Stethoscope}
            title={t("clinic.services.empty")}
            description={t("clinic.services.emptyBody")}
          />
        </div>
      ) : (
        <ul className="mt-3 flex flex-col gap-2">
          {(services.data ?? []).map((service) => (
            <li key={service.id}>
              <ServiceRow clinicId={clinicId} service={service} onRemoved={() => remove.mutate(service.id)} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function ServiceRow({
  clinicId,
  service,
  onRemoved,
}: {
  clinicId: string;
  service: ClinicService;
  onRemoved: () => void;
}) {
  const { t, formatCurrency } = useI18n();
  const queryClient = useQueryClient();
  const [price, setPrice] = useState(service.price);
  const save = useMutation({
    mutationFn: () => updateClinicService(clinicId, service.id, Number(price)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["clinic-services", clinicId] }),
  });
  const changed = Number(price) !== Number(service.price);

  return (
    <Card className="text-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-bold text-ink">{service.procedure_name}</p>
          <p className="mt-0.5 text-xs text-ink-muted">
            {service.doctor_name} · {formatCurrency(service.price)}
          </p>
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
          label={t("clinic.services.price")}
          type="number"
          inputMode="decimal"
          min={0}
          className="flex-1"
          value={price}
          onChange={(event) => setPrice(event.target.value)}
        />
        <Button
          variant="secondary"
          className="h-11 w-auto px-3 text-xs"
          disabled={!changed || save.isPending}
          onClick={() => save.mutate()}
        >
          {save.isPending ? t("clinic.saving") : t("clinic.services.save")}
        </Button>
      </div>
    </Card>
  );
}
