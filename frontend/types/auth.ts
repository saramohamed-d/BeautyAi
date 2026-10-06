import type { ClinicMembership } from "@/types/clinic";
import type { Doctor } from "@/types/doctor";
import type { Language, Patient } from "@/types/patient";

export type UserRole = "patient" | "doctor" | "clinic_admin" | "platform_admin";
export type UserStatus = "active" | "pending" | "suspended";

export interface AuthUser {
  id: string;
  email: string | null;
  phone: string | null;
  role: UserRole;
  status: UserStatus;
  /** Null until the address has been confirmed with a code (Sprint 17). */
  email_verified_at: string | null;
  phone_verified_at: string | null;
  created_at: string;
}

export interface Me {
  user: AuthUser;
  patient: Patient | null;
  /** Set for role=doctor: the dashboard needs the verification status. */
  doctor?: Doctor | null;
  /** Set for role=clinic_admin: the clinics whose dashboard they can open. */
  clinics?: ClinicMembership[];
}

export interface SessionResponse extends Me {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface RegisterInput {
  full_name: string;
  email: string;
  phone: string;
  password: string;
  preferred_language?: Language;
}

export interface DoctorRegisterInput {
  full_name: string;
  email: string;
  phone: string;
  password: string;
  specialty: string;
  sub_specialty?: string;
  license_number: string;
  years_experience?: number;
  medical_degree?: string;
  university?: string;
  city?: string;
  avatar?: string;
}
