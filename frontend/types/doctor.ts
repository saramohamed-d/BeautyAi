import type { Availability } from "@/types/availability";

export type VerificationStatus = "pending" | "verified" | "rejected";

export interface Doctor {
  id: string;
  full_name: string;
  specialty: string;
  sub_specialty?: string | null;
  license_number?: string | null;
  medical_degree?: string | null;
  university?: string | null;
  city?: string | null;
  bio?: string | null;
  years_experience?: number | null;
  rating?: number | null;
  phone?: string | null;
  email?: string | null;
  verification_status: VerificationStatus;
  /** Null until the doctor sends their application in for review. */
  submitted_at?: string | null;
  reviewed_at?: string | null;
  /** The admin's reason, shown to the doctor when rejected. */
  verification_notes?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export type DocumentType = "medical_license" | "medical_degree" | "national_id" | "specialty_certificate";
export type DocumentStatus = "pending" | "accepted" | "rejected";

export interface DoctorDocument {
  id: string;
  doctor_id: string;
  document_type: DocumentType;
  status: DocumentStatus;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  review_notes: string | null;
  created_at: string;
}

export interface ClinicSummary {
  id: string;
  name: string;
  city: string;
}

export interface DoctorSearchResult {
  doctor: Doctor;
  next_slot: Availability | null;
  price_from: number | null;
  clinics: ClinicSummary[];
}
