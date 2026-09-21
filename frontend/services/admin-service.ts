import { apiFetch, buildQuery } from "@/lib/api-client";
import type { Paginated } from "@/types/common";
import type {
  AdminOverview,
  AdminUser,
  AuditEvent,
  DoctorApplication,
  NotificationChannel,
  NotificationRecord,
  NotificationStatus,
} from "@/types/admin";
import type { UserRole, UserStatus } from "@/types/auth";
import type { Payment, PaymentStatus } from "@/types/payment";
import type { Doctor } from "@/types/doctor";

export function fetchAdminOverview(): Promise<AdminOverview> {
  return apiFetch<AdminOverview>("/api/v1/admin/overview");
}

export interface UserListParams {
  page?: number;
  page_size?: number;
  role?: UserRole;
  status?: UserStatus;
  q?: string;
}

export function fetchUsers(params: UserListParams = {}): Promise<Paginated<AdminUser>> {
  return apiFetch<Paginated<AdminUser>>(`/api/v1/admin/users${buildQuery(params)}`);
}

export function setUserStatus(userId: string, status: UserStatus, reason?: string): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/api/v1/admin/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify({ status, ...(reason ? { reason } : {}) }),
  });
}

export interface AuditListParams {
  page?: number;
  page_size?: number;
  action?: string;
  resource_type?: string;
  resource_id?: string;
  actor_id?: string;
}

export function fetchAuditEvents(params: AuditListParams = {}): Promise<Paginated<AuditEvent>> {
  return apiFetch<Paginated<AuditEvent>>(`/api/v1/admin/audit-events${buildQuery(params)}`);
}

export function fetchPayments(params: { page?: number; page_size?: number; status?: PaymentStatus } = {}): Promise<
  Paginated<Payment>
> {
  return apiFetch<Paginated<Payment>>(`/api/v1/payments${buildQuery(params)}`);
}

export function refundPayment(paymentId: string, reason: string): Promise<Payment> {
  return apiFetch<Payment>(`/api/v1/admin/payments/${paymentId}/refund`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

/** The doctor verification queue (Sprint 12's API, reviewed here). */
export function fetchApplications(status = "pending"): Promise<Paginated<DoctorApplication>> {
  return apiFetch<Paginated<DoctorApplication>>(`/api/v1/doctors/applications${buildQuery({ status, page_size: 50 })}`);
}

export function decideApplication(doctorId: string, status: "verified" | "rejected", notes?: string): Promise<Doctor> {
  return apiFetch<Doctor>(`/api/v1/doctors/${doctorId}/verification`, {
    method: "POST",
    body: JSON.stringify({ status, ...(notes ? { notes } : {}) }),
  });
}

export interface NotificationListParams {
  page?: number;
  page_size?: number;
  status?: NotificationStatus;
  channel?: NotificationChannel;
}

export function fetchNotifications(params: NotificationListParams = {}): Promise<Paginated<NotificationRecord>> {
  return apiFetch<Paginated<NotificationRecord>>(`/api/v1/admin/notifications${buildQuery(params)}`);
}

/** Sends everything that is due now instead of waiting for the scheduled run. */
export function dispatchNotifications(): Promise<{ sent: number; failed: number }> {
  return apiFetch<{ sent: number; failed: number }>("/api/v1/admin/notifications/dispatch", { method: "POST" });
}
