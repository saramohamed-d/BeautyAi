import { apiFetch, buildQuery } from "@/lib/api-client";
import type { Paginated } from "@/types/common";
import type { BookingReservation, ChatTurn, Conversation, ConversationDetail, Intake } from "@/types/chat";

export function listConversations(params: { page_size?: number } = {}): Promise<Paginated<Conversation>> {
  return apiFetch<Paginated<Conversation>>(`/api/v1/conversations${buildQuery(params)}`);
}

export function getConversation(id: string): Promise<ConversationDetail> {
  return apiFetch<ConversationDetail>(`/api/v1/conversations/${id}`);
}

export function startConversation(input: { accept_ai_terms: boolean; language: "en" | "ar" }): Promise<Conversation> {
  return apiFetch<Conversation>("/api/v1/conversations", { method: "POST", body: JSON.stringify({ channel: "web", ...input }) });
}

export function sendChatMessage(conversationId: string, content: string): Promise<ChatTurn> {
  return apiFetch<ChatTurn>(`/api/v1/conversations/${conversationId}/chat`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

/** The consultation (intake) of one of the patient's conversations, if it has started. */
export async function getConversationIntake(conversationId: string): Promise<Intake | null> {
  const page = await apiFetch<Paginated<Intake>>(`/api/v1/intakes${buildQuery({ conversation_id: conversationId })}`);
  return page.items[0] ?? null;
}

/** Reserve (hold) one of the booking agent's options; the patient confirms on the payment screen. */
export function reserveBookingOption(conversationId: string, availabilityId: string): Promise<BookingReservation> {
  return apiFetch<BookingReservation>(`/api/v1/conversations/${conversationId}/booking/reserve`, {
    method: "POST",
    body: JSON.stringify({ availability_id: availabilityId }),
  });
}
