export type Language = "ar" | "en";

export interface Patient {
  id: string;
  full_name: string;
  phone: string;
  email?: string | null;
  date_of_birth?: string | null;
  gender?: string | null;
  city?: string | null;
  preferred_language: Language;
  /** Which channels this patient wants (Sprint 15). */
  notify_email: boolean;
  notify_sms: boolean;
  notify_whatsapp: boolean;
  created_at: string;
  updated_at: string;
}
