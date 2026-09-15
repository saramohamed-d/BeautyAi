export type VerificationStatus = "pending" | "verified" | "rejected";

export interface Doctor {
  id: string;
  full_name: string;
  specialty: string;
  bio?: string | null;
  years_experience?: number | null;
  rating?: number | null;
  phone?: string | null;
  email?: string | null;
  verification_status: VerificationStatus;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
