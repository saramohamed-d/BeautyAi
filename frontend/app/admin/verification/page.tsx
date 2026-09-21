"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, FileText } from "lucide-react";
import { AdminShell } from "@/components/admin/admin-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useI18n } from "@/lib/i18n/provider";
import { ApiError } from "@/lib/api-client";
import { LIVE } from "@/lib/query-options";
import { decideApplication, fetchApplications } from "@/services/admin-service";
import { fetchDocumentFile } from "@/services/doctor-service";
import type { DoctorApplication } from "@/types/admin";
import type { DocumentType } from "@/types/doctor";
import type { MessageKey } from "@/lib/i18n/types";

const DOCUMENT_LABELS: Record<DocumentType, MessageKey> = {
  medical_license: "verification.docLicense",
  national_id: "verification.docId",
  medical_degree: "verification.docDegree",
  specialty_certificate: "verification.docCertificate",
};

/** The doctor verification queue: read the documents, then approve or reject (Sprints 12 + 14). */
export default function AdminVerificationPage() {
  return <AdminShell>{() => <Queue />}</AdminShell>;
}

function Queue() {
  const { t } = useI18n();
  const applications = useQuery({ queryKey: ["doctor-applications"], queryFn: () => fetchApplications(), ...LIVE });

  if (applications.isLoading) return <Skeleton className="h-64" />;
  const items = applications.data?.items ?? [];

  return (
    <>
      <h2 className="text-lg font-bold text-ink">{t("admin.verification.title")}</h2>
      <p className="mt-1 text-sm text-ink-muted">{t("admin.verification.subtitle")}</p>

      {items.length === 0 ? (
        <div className="mt-3">
          <EmptyState
            icon={BadgeCheck}
            title={t("admin.verification.empty")}
            description={t("admin.verification.emptyBody")}
          />
        </div>
      ) : (
        <ul className="mt-3 flex flex-col gap-2">
          {items.map((application) => (
            <li key={application.doctor.id}>
              <ApplicationCard application={application} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function ApplicationCard({ application }: { application: DoctorApplication }) {
  const { t, formatDate } = useI18n();
  const queryClient = useQueryClient();
  const { doctor, documents } = application;
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<"verified" | "rejected" | null>(null);

  const decide = useMutation({
    mutationFn: (status: "verified" | "rejected") => decideApplication(doctor.id, status, reason || undefined),
    onSuccess: (_result, status) => {
      setDone(status);
      queryClient.invalidateQueries({ queryKey: ["doctor-applications"] });
      queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : t("errors.generic")),
  });

  async function open(documentId: string, filename: string) {
    try {
      const blob = await fetchDocumentFile(doctor.id, documentId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setError(t("errors.generic"));
    }
  }

  if (done) {
    return (
      <Card className="text-sm">
        <p className="font-bold text-ink">{doctor.full_name}</p>
        <p className="mt-1 text-xs text-ink-muted">
          {done === "verified" ? t("admin.verification.approved") : t("admin.verification.rejectedDone")}
        </p>
      </Card>
    );
  }

  return (
    <Card className="text-sm">
      <p className="font-bold text-ink">{doctor.full_name}</p>
      <p className="mt-0.5 text-xs text-ink-muted">
        {doctor.specialty}
        {doctor.sub_specialty ? ` · ${doctor.sub_specialty}` : ""}
        {doctor.city ? ` · ${doctor.city}` : ""}
      </p>
      <dl className="mt-2 grid grid-cols-2 gap-1 text-xs">
        <dt className="text-ink-muted">{t("admin.verification.licence")}</dt>
        <dd className="font-medium text-ink" dir="ltr">
          {doctor.license_number ?? "—"}
        </dd>
        <dt className="text-ink-muted">{t("admin.verification.submitted")}</dt>
        <dd className="font-medium text-ink">
          {doctor.submitted_at ? formatDate(new Date(doctor.submitted_at), "long") : "—"}
        </dd>
      </dl>

      <p className="mt-2 text-xs font-bold text-ink">{t("admin.verification.documents")}</p>
      <ul className="mt-1 flex flex-wrap gap-1.5">
        {documents.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => open(item.id, item.original_filename)}
              className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-1 text-xs font-semibold text-primary-dark hover:border-primary-line"
            >
              <FileText className="h-3 w-3" aria-hidden="true" />
              {t(DOCUMENT_LABELS[item.document_type])}
            </button>
          </li>
        ))}
      </ul>

      <Input
        label={t("admin.verification.rejectReason")}
        className="mt-2"
        value={reason}
        onChange={(event) => {
          setError(null);
          setReason(event.target.value);
        }}
      />
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}
      <div className="mt-2 flex gap-2">
        <Button className="h-10 flex-1 text-xs" disabled={decide.isPending} onClick={() => decide.mutate("verified")}>
          {decide.isPending ? t("admin.verification.deciding") : t("admin.verification.approve")}
        </Button>
        <Button
          variant="secondary"
          className="h-10 flex-1 text-xs"
          disabled={decide.isPending}
          onClick={() => {
            if (!reason.trim()) {
              setError(t("admin.verification.rejectReasonRequired"));
              return;
            }
            decide.mutate("rejected");
          }}
        >
          {t("admin.verification.reject")}
        </Button>
      </div>
    </Card>
  );
}
