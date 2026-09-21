export interface Clinic {
  id: string;
  name: string;
  description?: string | null;
  address?: string | null;
  city: string;
  country: string;
  latitude?: number | null;
  longitude?: number | null;
  phone?: string | null;
  email?: string | null;
  cancellation_cutoff_hours: number;
  /** Default slot length when generating from the opening hours. */
  slot_duration_minutes: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ClinicMembership {
  id: string;
  name: string;
  city: string;
}

export type ClinicStaffRole = "doctor" | "clinic_admin";

export interface ClinicStaffMember {
  id: string;
  clinic_id: string;
  doctor_id: string | null;
  role: ClinicStaffRole;
  full_name: string;
  email: string | null;
  phone: string | null;
  /** The doctor's consultation fee here; null = the clinic confirms the price. */
  consultation_fee: string | null;
  is_active: boolean;
  created_at: string;
  verification_status: "pending" | "verified" | "rejected" | null;
  specialty: string | null;
}

/** 0 = Monday … 6 = Sunday. Times are clinic-local, "HH:MM:SS". */
export interface ClinicHours {
  weekday: number;
  opens_at: string;
  closes_at: string;
  is_closed: boolean;
}

export interface ClinicService {
  id: string;
  clinic_id: string;
  doctor_id: string;
  procedure_id: string;
  price: string;
  currency: string;
  created_at: string;
  doctor_name: string | null;
  procedure_name: string | null;
}

export interface SlotGenerateResult {
  created: number;
  skipped_existing: number;
  closed_days: number;
  slot_minutes: number;
}

export interface ClinicSummary {
  today: number;
  upcoming: number;
  pending: number;
  doctors: number;
  services: number;
  open_slots: number;
}
