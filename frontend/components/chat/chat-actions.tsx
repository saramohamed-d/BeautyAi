"use client";

import { createContext, useContext } from "react";

/**
 * Lets cards inside the chat (summary, booking options) send a message on
 * the patient's behalf, e.g. "Find me a slot". Outside a chat it's null
 * and those cards fall back to links.
 */
export const ChatActionsContext = createContext<{ send: (text: string) => void } | null>(null);

export function useChatActions() {
  return useContext(ChatActionsContext);
}
