import { apiFetch, buildQuery } from "@/lib/api-client";
import type { Paginated } from "@/types/common";
import type { KnowledgeDocument, KnowledgeDocumentSummary } from "@/types/knowledge";

export function listKnowledgeDocuments(params: { language?: "en" | "ar"; page_size?: number } = {}) {
  return apiFetch<Paginated<KnowledgeDocumentSummary>>(`/api/v1/knowledge/documents${buildQuery(params)}`);
}

export function getKnowledgeDocument(id: string) {
  return apiFetch<KnowledgeDocument>(`/api/v1/knowledge/documents/${id}`);
}
