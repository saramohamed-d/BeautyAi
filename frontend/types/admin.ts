import type { UserRole, UserStatus } from "@/types/auth";

export interface AdminUser {
  id: string;
  email: string | null;
  phone: string | null;
  role: UserRole;
  status: UserStatus;
  created_at: string;
  full_name: string | null;
  last_login_at: string | null;
}

export type ActorType = "patient" | "doctor" | "clinic_admin" | "platform_admin" | "system";

export interface AuditEvent {
  id: string;
  actor_type: ActorType;
  actor_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  extra_data: Record<string, unknown> | null;
  created_at: string;
}

export interface DailyPoint {
  date: string;
  bookings: number;
  revenue: string;
}

export interface AdminOverview {
  users: { total: number; by_role: Record<string, number>; suspended: number; new_this_month: number };
  doctors: { by_status: Record<string, number>; awaiting_review: number };
  clinics: { total: number; active: number };
  appointments: { by_status: Record<string, number>; upcoming: number };
  payments: {
    paid_total: string;
    paid_this_month: string;
    refunded_total: string;
    due_at_clinic: number;
    needs_refund: number;
  };
  /** What needs a human today; drives the badges on the dashboard. */
  attention: {
    doctor_applications: number;
    safety_events: number;
    knowledge_review: number;
    documents_pending: number;
    needs_refund: number;
  };
  daily: DailyPoint[];
}

export interface DoctorApplication {
  doctor: import("@/types/doctor").Doctor;
  documents: import("@/types/doctor").DoctorDocument[];
}

export type NotificationChannel = "email" | "sms" | "whatsapp";
export type NotificationStatus = "pending" | "sent" | "failed" | "skipped" | "cancelled";

export interface NotificationRecord {
  id: string;
  channel: NotificationChannel;
  status: NotificationStatus;
  template: string;
  language: string;
  recipient: string;
  subject: string | null;
  body: string;
  patient_id: string | null;
  appointment_id: string | null;
  scheduled_for: string;
  sent_at: string | null;
  attempts: number;
  provider: string | null;
  error: string | null;
}
