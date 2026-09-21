import { useQuery } from "@tanstack/react-query";
import { getKnowledgeDocument, listKnowledgeDocuments } from "@/services/knowledge-service";

export function useKnowledgeDocuments(language?: "en" | "ar") {
  return useQuery({
    queryKey: ["knowledge-documents", language],
    queryFn: () => listKnowledgeDocuments({ language, page_size: 100 }),
  });
}

export function useKnowledgeDocument(id: string | undefined) {
  return useQuery({
    queryKey: ["knowledge-document", id],
    queryFn: () => getKnowledgeDocument(id as string),
    enabled: Boolean(id),
  });
}
