export interface TicketSummary {
  id: number;
  kosin_id: string;
  source_system: string;
  summary: string;
  status: "open" | "in_progress" | "resolved" | "closed";
  priority: "low" | "medium" | "high" | "critical";
  created_at: string;
}

export interface TicketDetail extends TicketSummary {
  source_ticket_id: string;
  anonymized_description: string;
  closed_at: string | null;
  chat_history: ChatMessage[];
}

export interface ChatMessage {
  role: "operator" | "agent";
  content: string;
  timestamp: string;
}

export interface WSMessage {
  type: "token" | "complete" | "error" | "info";
  data: string;
  ticket_id: number | null;
}

export interface BoardTicket {
  key: string;
  priority: string;
  status: string;
  issue_type: string;
  already_ingested: boolean;
  source_system: string;
}
