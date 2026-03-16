export interface TicketSummary {
  id: number;
  kosin_id: string;
  source_system: string;
  source_ticket_id: string;
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

export interface AgentConfig {
  provider: string;
  model: string;
  temperature: number;
  system_prompt: string;
  available_providers: string[];
  tools: AgentTool[];
  ollama_config?: { base_url: string; available_models: string[] };
  openai_config?: { api_key_masked: string; model: string; available_models: string[] };
  azure_config?: { endpoint_masked: string; deployment: string; api_version: string };
  axet_config?: { project_id: string; asset_id: string };
}

export interface AgentTool {
  name: string;
  description: string;
  enabled: boolean;
}

export interface IntegrationConfig {
  id: number;
  system_name: string;
  display_name: string;
  system_type: string;
  connector_type: string;
  base_url: string;
  auth_token_masked: string;
  auth_email: string;
  project_key: string;
  extra_config: Record<string, string>;
  is_active: boolean;
  is_mock: boolean;
  polling_interval_sec: number;
  last_connection_test: string | null;
  last_connection_status: string | null;
  last_connection_error: string | null;
}
