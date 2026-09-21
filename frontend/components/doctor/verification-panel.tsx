"use client";

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock, FileText, Trash2, Upload, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Notice } from "@/components/ui/notice";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/lib/i18n/provider";
import { ApiError } from "@/lib/api-client";
import {
  deleteDoctorDocument,
  fetchDoctorDocuments,
  fetchDocumentFile,
  submitApplication,
  uploadDoctorDocument,
} from "@/services/doctor-service";
import type { Doctor, DocumentType } from "@/types/doctor";
import type { MessageKey } from "@/lib/i18n/types";

// The first two are required before an application can be submitted
// (backend REQUIRED_DOCUMENTS).
const DOCUMENT_TYPES: { id: DocumentType; label: MessageKey; required: boolean }[] = [
  { id: "medical_license", label: "verification.docLicense", required: true },
  { id: "national_id", label: "verification.docId", required: true },
  { id: "medical_degree", label: "verification.docDegree", required: false },
  { id: "specialty_certificate", label: "verification.docCertificate", required: false },
];

const ACCEPT = "application/pdf,image/jpeg,image/png,image/webp";

/** Upload, review and submit the verification documents (Sprint 12). */
export function VerificationPanel({ doctor, onSubmitted }: { doctor: Doctor; onSubmitted: () => void }) {
  const { t, formatDate } = useI18n();
  const queryClient = useQueryClient();
  const inputs = useRef<Record<string, HTMLInputElement | null>>({});
  const [error, setError] = useState<string | null>(null);
  const [busyType, setBusyType] = useState<DocumentType | null>(null);

  const documents = useQuery({
    queryKey: ["doctor-documents", doctor.id],
    queryFn: () => fetchDoctorDocuments(doctor.id),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["doctor-documents", doctor.id] });

  const upload = useMutation({
    mutationFn: ({ type, file }: { type: DocumentType; file: File }) => uploadDoctorDocument(doctor.id, type, file),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (documentId: string) => deleteDoctorDocument(doctor.id, documentId),
    onSuccess: invalidate,
  });
  const submit = useMutation({
    mutationFn: () => submitApplication(doctor.id),
    onSuccess: () => {
      invalidate();
      onSubmitted();
    },
  });

  async function onPick(type: DocumentType, file: File | undefined) {
    if (!file) return;
    setError(null);
    setBusyType(type);
    try {
      await upload.mutateAsync({ type, file });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("errors.generic"));
    }
    setBusyType(null);
    const input = inputs.current[type];
    if (input) input.value = "";
  }

  async function onDownload(documentId: string, filename: string) {
    setError(null);
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

  async function onSubmitApplication() {
    setError(null);
    try {
      await submit.mutateAsync();
    } catch (err) {
      setError(
        err instanceof ApiError && err.code === "missing_documents"
          ? t("verification.missingDocuments")
          : err instanceof ApiError && err.code === "already_submitted"
            ? t("verification.alreadySubmitted")
            : t("errors.generic")
      );
    }
  }

  const items = documents.data ?? [];
  const uploadedTypes = new Set(items.map((item) => item.document_type));
  const canSubmit = DOCUMENT_TYPES.filter((type) => type.required).every((type) => uploadedTypes.has(type.id));
  const underReview = doctor.verification_status === "pending" && Boolean(doctor.submitted_at);
  const locked = doctor.verification_status === "verified";

  return (
    <section aria-labelledby="documents-heading">
      <h2 id="documents-heading" className="mt-6 text-lg font-bold text-ink">
        {t("verification.documentsTitle")}
      </h2>
      <p className="mt-1 text-sm text-ink-muted">{t("verification.documentsHelp")}</p>

      {documents.isLoading ? (
        <Skeleton className="mt-3 h-40" />
      ) : (
        <div className="mt-3 flex flex-col gap-2">
          {DOCUMENT_TYPES.map(({ id, label, required }) => {
            const uploaded = items.filter((item) => item.document_type === id);
            return (
              <Card key={id} className="text-sm">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-bold text-ink">
                    {t(label)}
                    {required && <span className="text-primary-dark"> *</span>}
                  </p>
                  {!locked && (
                    <>
                      <input
                        ref={(element) => {
                          inputs.current[id] = element;
                        }}
                        id={`upload-${id}`}
                        type="file"
                        accept={ACCEPT}
                        className="sr-only"
                        onChange={(event) => onPick(id, event.target.files?.[0])}
                      />
                      <Button
                        type="button"
                        variant="secondary"
                        className="h-9 w-auto px-3 text-xs"
                        disabled={busyType === id}
                        onClick={() => inputs.current[id]?.click()}
                      >
                        <Upload className="h-3.5 w-3.5" aria-hidden="true" />
                        {busyType === id ? t("verification.uploading") : t("verification.upload")}
                      </Button>
                    </>
                  )}
                </div>

                {uploaded.length === 0 ? (
                  <p className="mt-1 text-xs text-ink-muted">{t("verification.notUploaded")}</p>
                ) : (
                  <ul className="mt-2 flex flex-col gap-1.5">
                    {uploaded.map((item) => (
                      <li key={item.id} className="flex items-center gap-2 text-xs text-ink-muted">
                        <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                        <button
                          type="button"
                          className="min-w-0 flex-1 truncate text-start font-medium text-primary-dark hover:underline"
                          onClick={() => onDownload(item.id, item.original_filename)}
                        >
                          {item.original_filename}
                        </button>
                        <span>{formatDate(new Date(item.created_at))}</span>
                        {item.status === "accepted" && (
                          <CheckCircle2 className="h-3.5 w-3.5 text-green-700" aria-label={t("verification.accepted")} />
                        )}
                        {item.status === "rejected" && (
                          <XCircle className="h-3.5 w-3.5 text-red-700" aria-label={t("verification.rejected")} />
                        )}
                        {!locked && (
                          <button
                            type="button"
                            aria-label={t("verification.remove")}
                            className="text-ink-muted hover:text-red-700"
                            onClick={() => remove.mutate(item.id)}
                          >
                            <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                {uploaded.some((item) => item.review_notes) && (
                  <p className="mt-1.5 text-xs text-ink">
                    {uploaded.find((item) => item.review_notes)?.review_notes}
                  </p>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {error && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {error}
        </p>
      )}

      {!locked &&
        (underReview ? (
          <Notice className="mt-[15px] flex items-start gap-2">
            <Clock className="mt-0.5 h-4 w-4 shrink-0 text-primary-dark" aria-hidden="true" />
            <span>{t("verification.underReviewNote")}</span>
          </Notice>
        ) : (
          <>
            <Button block className="mt-[15px]" disabled={!canSubmit || submit.isPending} onClick={onSubmitApplication}>
              {submit.isPending ? t("verification.submitting") : t("verification.submit")}
            </Button>
            {!canSubmit && <p className="mt-2 text-center text-xs text-ink-muted">{t("verification.missingDocuments")}</p>}
          </>
        ))}
    </section>
  );
}
