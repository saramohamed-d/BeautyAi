import { apiFetch, apiFetchBlob, buildQuery } from "@/lib/api-client";
import type { Paginated } from "@/types/common";
import type { Doctor, DoctorDocument, DocumentType, DoctorSearchResult } from "@/types/doctor";

export interface DoctorListParams {
  page?: number;
  page_size?: number;
  specialty?: string;
  is_active?: boolean;
}

export async function fetchDoctors(params: DoctorListParams = {}): Promise<Paginated<Doctor>> {
  return apiFetch<Paginated<Doctor>>(`/api/v1/doctors${buildQuery(params)}`);
}

export async function fetchDoctor(id: string): Promise<Doctor> {
  return apiFetch<Doctor>(`/api/v1/doctors/${id}`);
}

export interface DoctorSearchParams {
  page?: number;
  page_size?: number;
  q?: string;
  specialty?: string;
  city?: string;
  procedure_id?: string;
  max_price?: number;
  available_before?: string;
  sort?: "soonest" | "rating" | "price";
}

export async function searchDoctors(params: DoctorSearchParams = {}): Promise<Paginated<DoctorSearchResult>> {
  return apiFetch<Paginated<DoctorSearchResult>>(`/api/v1/doctors/search${buildQuery(params)}`);
}


// --- Verification (Sprint 12) ------------------------------------------------

export function fetchDoctorDocuments(doctorId: string): Promise<DoctorDocument[]> {
  return apiFetch<DoctorDocument[]>(`/api/v1/doctors/${doctorId}/documents`);
}

export function uploadDoctorDocument(
  doctorId: string,
  documentType: DocumentType,
  file: File
): Promise<DoctorDocument> {
  const form = new FormData();
  form.append("document_type", documentType);
  form.append("file", file);
  return apiFetch<DoctorDocument>(`/api/v1/doctors/${doctorId}/documents`, { method: "POST", body: form });
}

export function deleteDoctorDocument(doctorId: string, documentId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/doctors/${doctorId}/documents/${documentId}`, { method: "DELETE" });
}

/** Documents are never public URLs: fetch with the token, then hand the browser a blob. */
export function fetchDocumentFile(doctorId: string, documentId: string): Promise<Blob> {
  return apiFetchBlob(`/api/v1/doctors/${doctorId}/documents/${documentId}/file`);
}

export function submitApplication(doctorId: string): Promise<Doctor> {
  return apiFetch<Doctor>(`/api/v1/doctors/${doctorId}/submit`, { method: "POST" });
}

export function updateDoctor(doctorId: string, patch: Partial<Doctor>): Promise<Doctor> {
  return apiFetch<Doctor>(`/api/v1/doctors/${doctorId}`, { method: "PATCH", body: JSON.stringify(patch) });
}
