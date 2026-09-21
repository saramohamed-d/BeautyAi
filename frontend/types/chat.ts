import type { Availability, SlotHold } from "@/types/availability";
import type { Clinic } from "@/types/clinic";
import type { Doctor } from "@/types/doctor";

export type ConversationStatus = "active" | "completed" | "escalated";
export type RiskLevel = "low" | "medium" | "high";

export interface ChatSuggestion {
  specialty: string;
  concern: string | null;
}

export type Urgency = "routine" | "soon" | "urgent";

export interface Assessment {
  summary: string;
  suggested_specialty: string;
  urgency: Urgency;
  visit_preparation: string[];
  watch_for: string[];
}

export interface IntakeData {
  concern: string | null;
  concern_detail: string | null;
  body_area: string | null;
  duration: string | null;
  symptoms: string[] | null;
  tried: string[] | null;
  goal: string | null;
  pregnancy_or_breastfeeding: boolean | null;
  medications_or_allergies: string | null;
}

/** The consultation checklist (backend: app/workflows/consultation.py). */
export interface ConsultationSummary {
  status: "in_progress" | "complete";
  missing_fields: string[];
  data: IntakeData | null;
  assessment: Assessment | null;
}

export const REQUIRED_FIELDS = ["concern", "body_area", "duration", "symptoms"] as const;

/** One time the booking agent offers (backend: app/workflows/booking_agent.py). */
export interface BookingOption {
  availability_id: string;
  start_time: string;
  end_time: string;
  doctor: { id: string; full_name: string; specialty: string; rating: number | null };
  clinic: { id: string; name: string; city: string };
  /** The consultation fee at this clinic; null when the clinic confirms it. */
  consultation_fee: number | null;
}

export interface BookingOffer {
  criteria: Record<string, string | null>;
  options: BookingOption[];
  relaxed: string[];
}

/** A knowledge-library article a reply is based on. */
export interface ChatSource {
  document_id: string;
  title: string;
  heading: string | null;
  language: "en" | "ar";
}

/** Structured data the backend attaches to assistant messages. */
export interface AssistantExtra {
  kind?: "reply" | "emergency" | "fallback" | "booking_hold";
  safety?: { level: RiskLevel; flags: string[] };
  suggestion?: ChatSuggestion | null;
  sources?: ChatSource[];
  assessment?: Assessment | null;
  booking?: BookingOffer | null;
  consultation?: { status: "in_progress" | "complete"; missing_fields: string[] };
  ai?: { provider: string; model: string; prompt_version: string } | null;
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  extra_data: AssistantExtra | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  patient_id: string | null;
  channel: "web" | "whatsapp";
  language: "ar" | "en";
  status: ConversationStatus;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: ChatMessage[];
}

export interface ChatTurn {
  user_message: ChatMessage;
  assistant_message: ChatMessage;
  conversation_status: ConversationStatus;
  safety_level: RiskLevel;
  suggestion: ChatSuggestion | null;
  ai_mode: "live" | "demo";
  degraded: boolean;
  sources: ChatSource[];
  consultation: ConsultationSummary | null;
}

export interface Intake {
  id: string;
  conversation_id: string;
  status: "in_progress" | "complete";
  concern: string | null;
  body_area: string | null;
  structured_data: { data?: IntakeData; assessment?: Assessment | null; completed_at?: string } | null;
  missing_fields: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface BookingReservation {
  hold: SlotHold;
  slot: Availability;
  doctor: Doctor;
  clinic: Clinic;
  message: ChatMessage;
}
