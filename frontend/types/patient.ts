export type Language = "ar" | "en";

export interface Patient {
  id: string;
  full_name: string;
  phone: string;
  email?: string | null;
  date_of_birth?: string | null;
  gender?: string | null;
  preferred_language: Language;
  created_at: string;
  updated_at: string;
}

export interface PatientCreateInput {
  full_name: string;
  phone: string;
  email?: string;
}
