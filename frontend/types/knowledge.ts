export type KnowledgeStatus = "draft" | "pending_review" | "approved" | "archived";

export interface KnowledgeDocumentSummary {
  id: string;
  slug: string | null;
  title: string;
  summary: string | null;
  language: "en" | "ar";
  specialty: string | null;
  source: string;
  status: KnowledgeStatus;
  reviewed_by: string | null;
  last_reviewed: string | null;
}

export interface KnowledgeDocument extends KnowledgeDocumentSummary {
  body: string | null;
  url: string | null;
  evidence_level: string;
  version: string;
  reviewed_at: string | null;
  updated_at: string;
}
