"use client";

import { useState, useEffect, useCallback } from "react";
import type { IntegrationConfig, AgentConfig, AgentTool } from "@/types";
import { Header } from "@/components/Header";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Tab = "general" | "anonymization" | "agent" | "integrations" | "tickets";

const IconShield = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
  </svg>
);
const IconSettings = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
  </svg>
);
const IconPlug = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2v5"/><path d="M6 7h12l-1 9H7L6 7z"/><path d="M9 16v3a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2v-3"/>
  </svg>
);
const IconDatabase = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
  </svg>
);
const IconBrain = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 110 2h-1.07A7.001 7.001 0 0113 22h-2a7.001 7.001 0 01-6.93-6H3a1 1 0 110-2h1a7 7 0 017-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 012-2z"/>
  </svg>
);
const IconCheck = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12"/>
  </svg>
);
const IconTrash = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
  </svg>
);

const tabs: { id: Tab; label: string; icon: JSX.Element }[] = [
  { id: "general", label: "General", icon: <IconSettings /> },
  { id: "anonymization", label: "Anonimizacion", icon: <IconShield /> },
  { id: "agent", label: "Agente", icon: <IconBrain /> },
  { id: "integrations", label: "Integraciones", icon: <IconPlug /> },
  { id: "tickets", label: "Tickets", icon: <IconDatabase /> },
];

const PRESIDIO_ENTITIES_META: { id: string; label: string; category: string }[] = [
  { id: "PERSONA", label: "Personas (NER)", category: "NLP" },
  { id: "UBICACION", label: "Ubicaciones", category: "NLP" },
  { id: "ORGANIZACION", label: "Organizaciones", category: "NLP" },
  { id: "EMAIL", label: "Emails", category: "Patron" },
  { id: "TELEFONO", label: "Telefonos", category: "Patron" },
  { id: "IBAN", label: "IBAN", category: "Patron" },
  { id: "IP", label: "Direcciones IP", category: "Patron" },
  { id: "DNI", label: "DNI / NIF / NIE / CIF", category: "Patron" },
  { id: "TARJETA_CREDITO", label: "Tarjetas de credito", category: "Patron" },
  { id: "FECHA", label: "Fechas", category: "NLP" },
  { id: "URL", label: "URLs", category: "Patron" },
];

const PII_RULES_META: { id: string; label: string; category: string }[] = [
  { id: "names", label: "Nombres y Apellidos", category: "Personal" },
  { id: "emails", label: "Emails", category: "Personal" },
  { id: "phones", label: "Telefonos", category: "Personal" },
  { id: "dni", label: "DNI / NIF / NIE", category: "Personal" },
  { id: "ips", label: "Direcciones IP", category: "Tecnico" },
  { id: "cards", label: "IBAN / Tarjetas", category: "Financiero" },
  { id: "addresses", label: "Direcciones postales", category: "Personal" },
  { id: "license_plates", label: "Matriculas", category: "Personal" },
];

const priorityConfig: Record<string, { bg: string; text: string; label: string }> = {
  critical: { bg: "bg-red-100 dark:bg-red-900/30", text: "text-red-700 dark:text-red-400", label: "Critica" },
  high: { bg: "bg-amber-100 dark:bg-amber-900/30", text: "text-amber-700 dark:text-amber-400", label: "Alta" },
  medium: { bg: "bg-blue-100 dark:bg-blue-900/30", text: "text-blue-700 dark:text-blue-400", label: "Media" },
  low: { bg: "bg-green-100 dark:bg-green-900/30", text: "text-green-700 dark:text-green-400", label: "Baja" },
};

const statusConfig: Record<string, { bg: string; text: string; label: string }> = {
  open: { bg: "bg-blue-100 dark:bg-blue-900/30", text: "text-blue-700 dark:text-blue-400", label: "Abierto" },
  in_progress: { bg: "bg-emerald-100 dark:bg-emerald-900/30", text: "text-emerald-700 dark:text-emerald-400", label: "En progreso" },
  resolved: { bg: "bg-slate-100 dark:bg-slate-700", text: "text-slate-600 dark:text-slate-300", label: "Resuelto" },
  closed: { bg: "bg-slate-100 dark:bg-slate-700", text: "text-slate-500 dark:text-slate-400", label: "Cerrado" },
};

interface AdminTicket {
  id: number;
  source_system: string;
  source_ticket_id: string;
  kosin_ticket_id: string;
  summary: string;
  status: string;
  priority: string;
  created_at: string;
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "Nunca";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Ahora";
  if (mins < 60) return `Hace ${mins} min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `Hace ${hours}h`;
  return `Hace ${Math.floor(hours / 24)}d`;
}

function statusDot(status: string | null): string {
  if (status === "connected") return "bg-green-500";
  if (status === "error") return "bg-red-500";
  return "bg-amber-500";
}

function systemBgColor(name: string): string {
  if (name === "kosin") return "bg-blue-600";
  if (name === "servicenow") return "bg-green-600";
  return "bg-orange-500";
}

// Shared CSS classes
const cardCls = "bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm";
const inputCls = "w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-slate-100 outline-none focus:ring-2 focus:ring-primary focus:border-transparent";
const labelCls = "block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1";
const h2Cls = "text-lg font-bold text-slate-900 dark:text-slate-100 mb-1";
const descCls = "text-sm text-slate-500 dark:text-slate-400";
const btnPrimary = "px-5 py-2 bg-primary text-white text-sm font-bold rounded-lg hover:bg-blue-600 transition-colors shadow-lg shadow-primary/20 disabled:opacity-50";

export default function ConfigPage() {
  const [activeTab, setActiveTab] = useState<Tab>("integrations");

  // Anonymization settings state
  const [detectorType, setDetectorType] = useState("composite");
  const [activeDetector, setActiveDetector] = useState("unknown");
  const [presidioAvailable, setPresidioAvailable] = useState(false);
  const [substitutionTechnique, setSubstitutionTechnique] = useState("synthetic");
  const [sensitivity, setSensitivity] = useState(65);
  const [piiStates, setPiiStates] = useState<Record<string, boolean>>({});
  const [anonLoaded, setAnonLoaded] = useState(false);
  const [anonSaving, setAnonSaving] = useState(false);
  const [anonSaved, setAnonSaved] = useState(false);
  const [anonOpenPanel, setAnonOpenPanel] = useState<"regex" | "presidio" | "llm" | "output" | null>(null);
  const [presidioSensitivity, setPresidioSensitivity] = useState(65);
  const [presidioEntities, setPresidioEntities] = useState<Record<string, boolean>>({
    PERSONA: true, UBICACION: true, ORGANIZACION: true, EMAIL: true,
    TELEFONO: true, IBAN: true, IP: true, DNI: true,
    TARJETA_CREDITO: true, FECHA: false, URL: false,
  });
  const [presidioExcludedWords, setPresidioExcludedWords] = useState<string[]>([]);
  const [presidioNewWord, setPresidioNewWord] = useState("");
  const [presidioMinLengths, setPresidioMinLengths] = useState<Record<string, number>>({
    PERSONA: 4, UBICACION: 5, ORGANIZACION: 4,
  });
  const [presidioModel, setPresidioModel] = useState("es_core_news_lg");

  // Anonymization LLM state
  const [anonLlmEnabled, setAnonLlmEnabled] = useState(false);
  const [anonLlmProvider, setAnonLlmProvider] = useState("openai");
  const [anonLlmModel, setAnonLlmModel] = useState("");
  const [anonLlmTemp, setAnonLlmTemp] = useState(0.0);
  const [anonLlmSaving, setAnonLlmSaving] = useState(false);
  const [anonLlmSaved, setAnonLlmSaved] = useState(false);
  const [anonLlmTestResult, setAnonLlmTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [anonLlmTesting, setAnonLlmTesting] = useState(false);
  const [anonLlmPrompt, setAnonLlmPrompt] = useState("");
  const [anonLlmDefaultPrompt, setAnonLlmDefaultPrompt] = useState("");
  const [anonLlmApiKey, setAnonLlmApiKey] = useState("");

  // Integrations state
  const [integrations, setIntegrations] = useState<IntegrationConfig[]>([]);
  const [expandedSystem, setExpandedSystem] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Record<string, string | number | boolean>>({});
  const [testingSystem, setTestingSystem] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<Record<string, { status: string; message: string }>>({});
  const [saving, setSaving] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newIntegration, setNewIntegration] = useState({
    system_name: "", display_name: "", system_type: "source", connector_type: "jira",
    base_url: "", auth_token: "", auth_email: "", project_key: "", is_active: true,
  });
  const [addingIntegration, setAddingIntegration] = useState(false);
  const [deletingIntegration, setDeletingIntegration] = useState<string | null>(null);
  const [confirmDeleteIntegration, setConfirmDeleteIntegration] = useState<string | null>(null);

  // General settings state
  const [pollingInterval, setPollingInterval] = useState(60);
  const [generalLoaded, setGeneralLoaded] = useState(false);
  const [darkMode, setDarkMode] = useState(false);

  // Agent settings state
  const [agentConfig, setAgentConfig] = useState<AgentConfig | null>(null);
  const [agentProvider, setAgentProvider] = useState("openai");
  const [agentModel, setAgentModel] = useState("");
  const [agentTemp, setAgentTemp] = useState(0.3);
  const [agentPrompt, setAgentPrompt] = useState("");
  const [agentPromptSaved, setAgentPromptSaved] = useState("");
  const [agentTools, setAgentTools] = useState<AgentTool[]>([]);
  const [agentSaving, setAgentSaving] = useState(false);
  const [agentSaved, setAgentSaved] = useState(false);
  const [promptSaving, setPromptSaving] = useState(false);
  const [promptSaved, setPromptSaved] = useState(false);
  const [openaiApiKey, setOpenaiApiKey] = useState("");
  const [axetBearerToken, setAxetBearerToken] = useState("");
  const [axetAssetId, setAxetAssetId] = useState("");
  const [axetProjectId, setAxetProjectId] = useState("");
  const [axetAuth, setAxetAuth] = useState<{ authenticated: boolean; user?: { displayName?: string; name?: string; email?: string; preferred_username?: string }; expires_in?: number; has_refresh_token?: boolean } | null>(null);
  const [axetAuthLoading, setAxetAuthLoading] = useState(false);
  const [axetDeviceCode, setAxetDeviceCode] = useState<{ user_code: string; verification_uri_complete: string } | null>(null);
  const [axetPolling, setAxetPolling] = useState(false);
  const [axetModels, setAxetModels] = useState<{ id: string; displayName: string }[]>([]);
  const [axetProjects, setAxetProjects] = useState<{ id: string; displayName: string }[]>([]);
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionResult, setConnectionResult] = useState<{ success: boolean; message: string } | null>(null);

  // Admin tickets state
  const [adminTickets, setAdminTickets] = useState<AdminTicket[]>([]);
  const [adminLoading, setAdminLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const fetchIntegrations = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/config/integrations`);
      if (res.ok) setIntegrations(await res.json());
    } catch (err) {
      console.error("Failed to fetch integrations:", err);
    }
  }, []);

  const fetchGeneralSettings = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/config/general`);
      if (res.ok) {
        const data = await res.json();
        setPollingInterval(data.polling_interval_sec || 60);
        const dm = data.dark_mode ?? false;
        setDarkMode(dm);
        // Sync with localStorage
        const localDark = localStorage.getItem("dark_mode") === "true";
        if (localDark !== dm) {
          // localStorage takes precedence on first load
          setDarkMode(localDark);
        }
        setGeneralLoaded(true);
      }
    } catch (err) {
      console.error("Failed to fetch general settings:", err);
      // Fallback to localStorage
      setDarkMode(localStorage.getItem("dark_mode") === "true");
      setGeneralLoaded(true);
    }
  }, []);

  const fetchAdminTickets = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/tickets`);
      if (res.ok) setAdminTickets(await res.json());
    } catch (err) {
      console.error("Failed to fetch admin tickets:", err);
    } finally {
      setAdminLoading(false);
    }
  }, []);

  const fetchAnonymization = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/config/anonymization`);
      if (res.ok) {
        const data = await res.json();
        setDetectorType(data.detector_type || "composite");
        setActiveDetector(data.active_detector || "unknown");
        setPresidioAvailable(data.presidio_available || false);
        setSensitivity(data.sensitivity ?? 65);
        setPresidioSensitivity(data.presidio_sensitivity ?? 65);
        if (data.presidio_entities) setPresidioEntities(data.presidio_entities);
        if (data.presidio_excluded_words) setPresidioExcludedWords(data.presidio_excluded_words);
        if (data.presidio_min_lengths) setPresidioMinLengths(data.presidio_min_lengths);
        if (data.presidio_model) setPresidioModel(data.presidio_model);
        setSubstitutionTechnique(data.substitution_technique || "synthetic");
        if (data.pii_rules) setPiiStates(data.pii_rules);
        setAnonLoaded(true);
      }
    } catch (err) {
      console.error("Failed to fetch anonymization settings:", err);
    }
  }, []);

  const fetchAnonLlmConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/config/anon-llm`);
      if (res.ok) {
        const data = await res.json();
        setAnonLlmEnabled(data.enabled ?? false);
        setAnonLlmProvider(data.provider || "openai");
        setAnonLlmModel(data.model || "");
        setAnonLlmTemp(data.temperature ?? 0.0);
        setAnonLlmPrompt(data.system_prompt || "");
        setAnonLlmDefaultPrompt(data.default_prompt || "");
      }
    } catch (err) {
      console.error("Failed to fetch anon LLM config:", err);
    }
  }, []);

  const fetchAgentConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/config/agent`);
      if (res.ok) {
        const data: AgentConfig = await res.json();
        setAgentConfig(data);
        setAgentProvider(data.provider);
        setAgentModel(data.model);
        setAgentTemp(data.temperature);
        setAgentPrompt(data.system_prompt);
        setAgentPromptSaved(data.system_prompt);
        setAgentTools(data.tools);
        // Restore Axet-specific fields from persisted config
        if (data.axet_config?.project_id) setAxetProjectId(data.axet_config.project_id);
        if (data.axet_config?.asset_id) setAxetAssetId(data.axet_config.asset_id);
      }
    } catch (err) {
      console.error("Failed to fetch agent config:", err);
    }
  }, []);

  useEffect(() => {
    fetchIntegrations();
    fetchGeneralSettings();
    fetchAdminTickets();
    fetchAnonymization();
    fetchAgentConfig();
    fetchAnonLlmConfig();
  }, [fetchIntegrations, fetchGeneralSettings, fetchAdminTickets, fetchAnonymization, fetchAgentConfig, fetchAnonLlmConfig]);

  // Axet OAuth: fetch auth status and listen for popup messages
  const fetchAxetAuthStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/axet/auth/status`);
      const data = await res.json();
      setAxetAuth(data);
    } catch {}
  }, []);

  const fetchAxetModels = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/axet/auth/models`);
      if (res.ok) {
        const data = await res.json();
        if (data.models?.length) {
          setAxetModels(data.models);
          // Sync agentModel: if current value doesn't match any loaded model id, select first
          setAgentModel((prev) => {
            const ids = data.models.map((m: { id: string }) => m.id);
            return ids.includes(prev) ? prev : data.models[0].id;
          });
        }
      }
    } catch {}
  }, []);

  const fetchAxetProjects = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/axet/auth/projects`);
      if (res.ok) {
        const data = await res.json();
        if (data.projects?.length) {
          setAxetProjects(data.projects);
          // Auto-select first project if none selected
          if (!axetProjectId && !agentConfig?.axet_config?.project_id) {
            setAxetProjectId(data.projects[0].id);
          }
        }
      }
    } catch {}
  }, [axetProjectId, agentConfig?.axet_config?.project_id]);

  useEffect(() => {
    fetchAxetAuthStatus();
  }, [fetchAxetAuthStatus]);

  useEffect(() => {
    if (axetAuth?.authenticated) {
      fetchAxetModels();
      fetchAxetProjects();
    }
  }, [axetAuth?.authenticated, fetchAxetModels, fetchAxetProjects]);

  const handleExpand = (systemName: string) => {
    if (expandedSystem === systemName) {
      setExpandedSystem(null);
      return;
    }
    const sys = integrations.find((s) => s.system_name === systemName);
    if (sys) {
      setEditForm({
        base_url: sys.base_url,
        auth_token: "",
        auth_email: sys.auth_email,
        project_key: sys.project_key,
        is_active: sys.is_active,
        polling_interval_sec: sys.polling_interval_sec,
        board_id: sys.extra_config?.board_id || "",
        issue_type_id: sys.extra_config?.issue_type_id || "",
        parent_key: sys.extra_config?.parent_key || "",
      });
    }
    setExpandedSystem(systemName);
    setTestResult((prev) => ({ ...prev, [systemName]: undefined as never }));
  };

  const handleSave = async (systemName: string) => {
    setSaving(true);
    try {
      const body: Record<string, unknown> = {};
      if (editForm.base_url !== undefined) body.base_url = editForm.base_url;
      if (editForm.auth_token && String(editForm.auth_token).length > 0) body.auth_token = editForm.auth_token;
      if (editForm.auth_email !== undefined) body.auth_email = editForm.auth_email;
      if (editForm.project_key !== undefined) body.project_key = editForm.project_key;
      body.is_active = editForm.is_active;
      body.polling_interval_sec = Number(editForm.polling_interval_sec);
      body.extra_config = {
        board_id: String(editForm.board_id || ""),
        issue_type_id: String(editForm.issue_type_id || ""),
        parent_key: String(editForm.parent_key || ""),
      };
      await fetch(`${API_URL}/api/config/integrations/${systemName}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      await fetchIntegrations();
      setExpandedSystem(null);
    } catch (err) {
      console.error("Failed to save:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async (systemName: string) => {
    setTestingSystem(systemName);
    setTestResult((prev) => ({ ...prev, [systemName]: undefined as never }));
    try {
      const res = await fetch(`${API_URL}/api/config/integrations/${systemName}/test`, { method: "POST" });
      const data = await res.json();
      setTestResult((prev) => ({ ...prev, [systemName]: { status: data.status, message: data.message } }));
      await fetchIntegrations();
    } catch (err) {
      setTestResult((prev) => ({ ...prev, [systemName]: { status: "error", message: "Error de red" } }));
    } finally {
      setTestingSystem(null);
    }
  };

  const handleAddIntegration = async () => {
    if (!newIntegration.system_name.trim() || !newIntegration.display_name.trim()) return;
    setAddingIntegration(true);
    try {
      const res = await fetch(`${API_URL}/api/config/integrations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newIntegration),
      });
      if (res.ok) {
        await fetchIntegrations();
        setShowAddForm(false);
        setNewIntegration({
          system_name: "", display_name: "", system_type: "source", connector_type: "jira",
          base_url: "", auth_token: "", auth_email: "", project_key: "", is_active: true,
        });
      } else {
        const err = await res.json();
        alert(err.detail || "Error al crear integracion");
      }
    } catch (err) {
      console.error("Failed to add integration:", err);
    } finally {
      setAddingIntegration(false);
    }
  };

  const handleDeleteIntegration = async (name: string) => {
    setDeletingIntegration(name);
    try {
      const res = await fetch(`${API_URL}/api/config/integrations/${name}`, { method: "DELETE" });
      if (res.ok) {
        await fetchIntegrations();
        if (expandedSystem === name) setExpandedSystem(null);
      }
    } catch (err) {
      console.error("Failed to delete integration:", err);
    } finally {
      setDeletingIntegration(null);
      setConfirmDeleteIntegration(null);
    }
  };

  const handleSaveGeneral = async () => {
    try {
      await fetch(`${API_URL}/api/config/general`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ polling_interval_sec: pollingInterval }),
      });
    } catch (err) {
      console.error("Failed to save general settings:", err);
    }
  };

  const handleToggleDarkMode = async () => {
    const newVal = !darkMode;
    setDarkMode(newVal);
    localStorage.setItem("dark_mode", String(newVal));
    document.documentElement.classList.toggle("dark", newVal);
    try {
      await fetch(`${API_URL}/api/config/general`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dark_mode: newVal }),
      });
    } catch (err) {
      console.error("Failed to save dark mode:", err);
    }
  };

  const handleDeleteTicket = async (kosinKey: string) => {
    setDeleting(kosinKey);
    setDeleteError(null);
    try {
      const res = await fetch(`${API_URL}/api/admin/tickets/${kosinKey}`, { method: "DELETE" });
      if (res.ok) {
        setAdminTickets((prev) => prev.filter((t) => t.kosin_ticket_id !== kosinKey));
        setConfirmDelete(null);
      } else {
        const err = await res.json();
        setDeleteError(err.detail || "Error desconocido");
      }
    } catch {
      setDeleteError("Error de red al eliminar el ticket");
    } finally {
      setDeleting(null);
    }
  };

  const handleSaveAnonymization = async () => {
    setAnonSaving(true);
    setAnonSaved(false);
    try {
      const res = await fetch(`${API_URL}/api/config/anonymization`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          detector_type: detectorType,
          sensitivity,
          presidio_sensitivity: presidioSensitivity,
          presidio_entities: presidioEntities,
          presidio_excluded_words: presidioExcludedWords,
          presidio_min_lengths: presidioMinLengths,
          presidio_model: presidioModel,
          pii_rules: piiStates,
          substitution_technique: substitutionTechnique,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.warning) console.warn("Anon save warning:", data.warning);
        setAnonSaved(true);
        setTimeout(() => setAnonSaved(false), 3000);
        await fetchAnonymization();
      }
    } catch (err) {
      console.error("Failed to save anonymization settings:", err);
    } finally {
      setAnonSaving(false);
    }
  };

  // Anon LLM handlers
  const handleSaveAnonLlm = async () => {
    setAnonLlmSaving(true);
    setAnonLlmSaved(false);
    try {
      const res = await fetch(`${API_URL}/api/config/anon-llm`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: anonLlmEnabled,
          provider: anonLlmProvider,
          model: anonLlmModel,
          temperature: anonLlmTemp,
          system_prompt: anonLlmPrompt,
          ...(anonLlmProvider === "openai" && anonLlmApiKey ? { api_key: anonLlmApiKey } : {}),
          ...(anonLlmProvider === "axet" && axetProjectId ? { axet_project_id: axetProjectId } : {}),
          ...(anonLlmProvider === "axet" && axetAssetId ? { axet_asset_id: axetAssetId } : {}),
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.warning) console.warn("Anon LLM save warning:", data.warning);
        setAnonLlmSaved(true);
        setTimeout(() => setAnonLlmSaved(false), 3000);
        await fetchAnonLlmConfig();
      }
    } catch (err) {
      console.error("Failed to save anon LLM config:", err);
    } finally {
      setAnonLlmSaving(false);
    }
  };

  const handleTestAnonLlm = async () => {
    setAnonLlmTesting(true);
    setAnonLlmTestResult(null);
    try {
      const res = await fetch(`${API_URL}/api/config/anon-llm/test-connection`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: anonLlmProvider,
          model: anonLlmModel,
          ...(anonLlmProvider === "openai" && anonLlmApiKey ? { api_key: anonLlmApiKey } : {}),
          ...(anonLlmProvider === "axet" && axetProjectId ? { axet_project_id: axetProjectId } : {}),
          ...(anonLlmProvider === "axet" && axetAssetId ? { axet_asset_id: axetAssetId } : {}),
        }),
      });
      const data = await res.json();
      setAnonLlmTestResult({ success: data.success, message: data.message });
    } catch {
      setAnonLlmTestResult({ success: false, message: "Error de red" });
    } finally {
      setAnonLlmTesting(false);
    }
  };

  // Agent handlers
  const handleSaveAgentLLM = async () => {
    setAgentSaving(true);
    setAgentSaved(false);
    try {
      const res = await fetch(`${API_URL}/api/config/agent`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: agentProvider,
          model: agentModel,
          temperature: agentTemp,
          ...(agentProvider === "axet" && axetProjectId ? { axet_project_id: axetProjectId } : {}),
          ...(agentProvider === "axet" && axetAssetId ? { axet_asset_id: axetAssetId } : {}),
        }),
      });
      if (res.ok) {
        setAgentSaved(true);
        setTimeout(() => setAgentSaved(false), 3000);
        await fetchAgentConfig();
      }
    } catch (err) {
      console.error("Failed to save agent LLM config:", err);
    } finally {
      setAgentSaving(false);
    }
  };

  const handleSavePrompt = async () => {
    setPromptSaving(true);
    setPromptSaved(false);
    try {
      const res = await fetch(`${API_URL}/api/config/agent`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ system_prompt: agentPrompt }),
      });
      if (res.ok) {
        setAgentPromptSaved(agentPrompt);
        setPromptSaved(true);
        setTimeout(() => setPromptSaved(false), 3000);
      }
    } catch (err) {
      console.error("Failed to save prompt:", err);
    } finally {
      setPromptSaving(false);
    }
  };

  const handleRestoreDefaultPrompt = async () => {
    try {
      const res = await fetch(`${API_URL}/api/config/agent/default-prompt`);
      if (res.ok) {
        const data = await res.json();
        setAgentPrompt(data.system_prompt);
      }
    } catch (err) {
      console.error("Failed to fetch default prompt:", err);
    }
  };

  const handleToggleTool = async (toolName: string, enabled: boolean) => {
    // Optimistic update
    setAgentTools((prev) => prev.map((t) => t.name === toolName ? { ...t, enabled } : t));
    try {
      await fetch(`${API_URL}/api/config/agent/tools`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tools: { [toolName]: enabled } }),
      });
    } catch (err) {
      // Revert
      setAgentTools((prev) => prev.map((t) => t.name === toolName ? { ...t, enabled: !enabled } : t));
      console.error("Failed to toggle tool:", err);
    }
  };


  const activeToolsCount = agentTools.filter((t) => t.enabled).length;
  const promptModified = agentPrompt !== agentPromptSaved;

  // ollama_config kept in backend but hidden from UI
  const tempLabel = agentTemp <= 0.2 ? "Preciso" : agentTemp <= 0.5 ? "Equilibrado" : agentTemp <= 0.8 ? "Creativo" : "Experimental";

  return (
    <div className="bg-[#F8FAFC] dark:bg-slate-900 text-slate-900 dark:text-slate-100 h-screen flex flex-col overflow-hidden">
      <Header
        activePage="config"
        subheader={
          <div className="flex items-center gap-3 text-sm font-medium">
            <span className="text-slate-400">Configuracion del Sistema</span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#475569" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
            <span className="text-slate-100">{tabs.find((t) => t.id === activeTab)?.label}</span>
          </div>
        }
      />

      {/* Content */}
      <div className="flex-1 flex min-h-0">
        {/* Sidebar */}
        <aside className="w-64 bg-white dark:bg-slate-800 border-r border-slate-200 dark:border-slate-700 p-4 shrink-0">
          <div className="space-y-1">
            {tabs.map((tab) => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? "bg-primary/10 text-primary border-r-2 border-primary"
                    : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"
                }`}>
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>
        </aside>

        {/* Main */}
        <main className="flex-1 overflow-y-auto p-8">
          <div className={activeTab === "tickets" ? "max-w-6xl" : "max-w-3xl"}>

            {/* ===== GENERAL TAB ===== */}
            {activeTab === "general" && (
              <div className="space-y-6">
                <div>
                  <h2 className={h2Cls}>Configuracion General</h2>
                  <p className={descCls}>Parametros generales de la plataforma.</p>
                </div>

                {/* Dark Mode */}
                <div className={`${cardCls} p-6`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">Modo oscuro</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Cambia la apariencia de toda la interfaz</p>
                    </div>
                    <button
                      onClick={handleToggleDarkMode}
                      className={`relative w-12 h-6 rounded-full transition-colors ${darkMode ? "bg-primary" : "bg-slate-300 dark:bg-slate-600"}`}
                    >
                      <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${darkMode ? "left-[26px]" : "left-0.5"}`} />
                    </button>
                  </div>
                </div>

                {/* Polling interval */}
                <div className={`${cardCls} p-6 space-y-4`}>
                  <div>
                    <label className={labelCls}>Intervalo de refresco del board (seg)</label>
                    <input
                      type="number"
                      min={5}
                      value={generalLoaded ? pollingInterval : 60}
                      onChange={(e) => setPollingInterval(Number(e.target.value))}
                      className={inputCls}
                    />
                  </div>
                </div>
                <div className="flex justify-end">
                  <button onClick={handleSaveGeneral} className={btnPrimary}>
                    Guardar configuracion
                  </button>
                </div>
              </div>
            )}

            {/* ===== AGENT TAB ===== */}
            {activeTab === "agent" && (
              <div className="space-y-8">
                {/* Section 1: Provider & Model */}
                <section>
                  <h2 className={h2Cls}>Proveedor y Modelo</h2>
                  <p className={`${descCls} mb-4`}>Configura el LLM que usa el agente de anonimizacion.</p>

                  {/* Provider radio cards */}
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    {[
                      { id: "openai", title: "OpenAI", desc: "API directa GPT", bgColor: "bg-slate-800 dark:bg-slate-600" },
                      { id: "axet", title: "Axet NTT", desc: "Proxy corporativo", bgColor: "bg-purple-600" },
                    ].map((p) => (
                      <button key={p.id} onClick={() => {
                        setAgentProvider(p.id);
                        setConnectionResult(null);
                        if (p.id === "openai") {
                          setAgentModel(agentConfig?.openai_config?.model || "gpt-4o-mini");
                        } else if (p.id === "axet") {
                          setAgentModel(agentConfig?.axet_config?.model || "gpt-4o-mini");
                        }
                      }}
                        className={`p-4 rounded-xl border text-left transition-all ${
                          agentProvider === p.id
                            ? "border-primary bg-primary/5 dark:bg-primary/10 shadow-sm"
                            : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:border-slate-300 dark:hover:border-slate-600"
                        }`}>
                        <div className="flex items-center gap-3">
                          <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-white text-sm font-bold ${p.bgColor}`}>
                            {p.id === "openai" ? (
                              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2a10 10 0 0110 10 10 10 0 01-10 10A10 10 0 012 12 10 10 0 0112 2z"/><path d="M8 12l2 2 4-4"/></svg>
                            ) : p.id === "axet" ? (
                              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
                            ) : (
                              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 10h-1.26A8 8 0 109 20h9a5 5 0 000-10z"/></svg>
                            )}
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{p.title}</p>
                            <p className="text-xs text-slate-500 dark:text-slate-400">{p.desc}</p>
                          </div>
                          <div className={`ml-auto w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 ${
                            agentProvider === p.id ? "border-primary bg-primary" : "border-slate-300 dark:border-slate-600"
                          }`}>
                            {agentProvider === p.id && <IconCheck />}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>

                  {/* Model selection */}
                  <div className={`${cardCls} p-5 space-y-4`}>
                    {agentProvider === "openai" ? (
                      <>
                        <div>
                          <label className={labelCls}>Modelo</label>
                          <select value={agentModel} onChange={(e) => setAgentModel(e.target.value)} className={inputCls}>
                            {(agentConfig?.openai_config?.available_models || ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]).map((m: string) => (
                              <option key={m} value={m}>{m}</option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className={labelCls}>API Key</label>
                          <div className="flex gap-2">
                            <input
                              type="password"
                              value={openaiApiKey}
                              onChange={(e) => setOpenaiApiKey(e.target.value)}
                              placeholder={agentConfig?.openai_config?.api_key_masked || "sk-..."}
                              className={`${inputCls} flex-1`}
                            />
                            <button
                              onClick={async () => {
                                if (!openaiApiKey) return;
                                try {
                                  await fetch(`${API_URL}/api/config/agent/api-key`, {
                                    method: "PUT",
                                    headers: { "Content-Type": "application/json" },
                                    body: JSON.stringify({ provider: "openai", api_key: openaiApiKey }),
                                  });
                                  setAgentSaved(true);
                                  setTimeout(() => setAgentSaved(false), 2000);
                                } catch {}
                              }}
                              className="px-3 py-2 text-xs font-bold text-white bg-primary rounded-lg hover:bg-primary/90 transition-colors shrink-0"
                            >
                              Aplicar
                            </button>
                          </div>
                          <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
                            {agentConfig?.openai_config?.api_key_masked ? "API key cargada desde .env" : "Introduce tu API key de OpenAI"}
                          </p>
                        </div>
                      </>
                    ) : agentProvider === "axet" ? (
                      <>
                        {/* OKTA Device Code Login */}
                        <div className={`p-4 rounded-lg border ${
                          axetAuth?.authenticated
                            ? "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800"
                            : axetDeviceCode
                              ? "bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800"
                              : "bg-slate-50 dark:bg-slate-900/50 border-slate-200 dark:border-slate-700"
                        }`}>
                          {axetAuth?.authenticated ? (
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3">
                                <div className="w-3 h-3 rounded-full bg-green-500 animate-pulse" />
                                <div>
                                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                                    Sesion activa — {axetAuth.user?.displayName || axetAuth.user?.name || axetAuth.user?.email || "Usuario"}
                                  </p>
                                  <p className="text-xs text-slate-500 dark:text-slate-400">
                                    Expira en {Math.floor((axetAuth.expires_in || 0) / 60)} min{axetAuth.has_refresh_token ? " (auto-renovable)" : ""}
                                  </p>
                                </div>
                              </div>
                              <div className="flex gap-2">
                                <button
                                  onClick={async () => {
                                    try {
                                      await fetch(`${API_URL}/api/axet/auth/refresh`, { method: "POST" });
                                      fetchAxetAuthStatus();
                                    } catch {}
                                  }}
                                  className="px-3 py-1.5 text-xs font-medium text-slate-600 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                                >
                                  Renovar
                                </button>
                                <button
                                  onClick={async () => {
                                    try {
                                      await fetch(`${API_URL}/api/axet/auth/logout`, { method: "POST" });
                                      setAxetAuth(null);
                                      fetchAxetAuthStatus();
                                    } catch {}
                                  }}
                                  className="px-3 py-1.5 text-xs font-medium text-red-600 dark:text-red-400 bg-white dark:bg-slate-800 border border-red-200 dark:border-red-800 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                                >
                                  Cerrar sesion
                                </button>
                              </div>
                            </div>
                          ) : axetDeviceCode ? (
                            <div className="text-center space-y-3">
                              <p className="text-sm text-slate-600 dark:text-slate-300">
                                Abre el siguiente enlace e introduce el codigo:
                              </p>
                              <div className="bg-white dark:bg-slate-900 rounded-lg p-3 border border-purple-200 dark:border-purple-700">
                                <p className="text-2xl font-mono font-bold tracking-widest text-purple-700 dark:text-purple-400">
                                  {axetDeviceCode.user_code}
                                </p>
                              </div>
                              <a
                                href={axetDeviceCode.verification_uri_complete}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-block px-4 py-2 text-sm font-bold text-white bg-purple-600 rounded-lg hover:bg-purple-700 transition-colors"
                              >
                                Abrir pagina de login OKTA
                              </a>
                              <div className="flex items-center justify-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                                <div className="w-3 h-3 border-2 border-purple-400 border-t-transparent rounded-full animate-spin" />
                                Esperando autenticacion...
                              </div>
                              <button
                                onClick={() => { setAxetDeviceCode(null); setAxetPolling(false); }}
                                className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                              >
                                Cancelar
                              </button>
                            </div>
                          ) : (
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3">
                                <div className="w-3 h-3 rounded-full bg-slate-400" />
                                <div>
                                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">No autenticado</p>
                                  <p className="text-xs text-slate-500 dark:text-slate-400">Inicia sesion con OKTA corporativo</p>
                                </div>
                              </div>
                              <button
                                disabled={axetAuthLoading}
                                onClick={async () => {
                                  setAxetAuthLoading(true);
                                  try {
                                    const res = await fetch(`${API_URL}/api/axet/auth/start`, { method: "POST" });
                                    const data = await res.json();
                                    if (data.user_code) {
                                      setAxetDeviceCode({ user_code: data.user_code, verification_uri_complete: data.verification_uri_complete });
                                      // Start polling
                                      setAxetPolling(true);
                                      const pollInterval = setInterval(async () => {
                                        try {
                                          const pollRes = await fetch(`${API_URL}/api/axet/auth/poll`, { method: "POST" });
                                          const pollData = await pollRes.json();
                                          if (pollData.status === "success") {
                                            clearInterval(pollInterval);
                                            setAxetDeviceCode(null);
                                            setAxetPolling(false);
                                            fetchAxetAuthStatus();
                                          } else if (pollData.status === "expired" || pollData.status === "error") {
                                            clearInterval(pollInterval);
                                            setAxetDeviceCode(null);
                                            setAxetPolling(false);
                                          }
                                        } catch {
                                          clearInterval(pollInterval);
                                          setAxetDeviceCode(null);
                                          setAxetPolling(false);
                                        }
                                      }, 5000);
                                    }
                                  } catch {}
                                  setAxetAuthLoading(false);
                                }}
                                className="px-4 py-1.5 text-xs font-bold text-white bg-purple-600 rounded-lg hover:bg-purple-700 transition-colors"
                              >
                                {axetAuthLoading ? "Iniciando..." : "Login con OKTA"}
                              </button>
                            </div>
                          )}
                        </div>

                        <div>
                          <label className={labelCls}>Modelo</label>
                          <select value={agentModel} onChange={(e) => setAgentModel(e.target.value)} className={inputCls}>
                            {axetModels.length > 0 ? (
                              axetModels.map((m) => <option key={m.id} value={m.id}>{m.displayName || m.id}</option>)
                            ) : (
                              ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"].map((m) => (
                                <option key={m} value={m}>{m}</option>
                              ))
                            )}
                          </select>
                          {axetAuth?.authenticated && axetModels.length === 0 && (
                            <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">Cargando modelos de Axet...</p>
                          )}
                        </div>

                        {/* Manual token fallback (collapsible) */}
                        {!axetAuth?.authenticated && (
                          <div>
                            <label className={labelCls}>Bearer Token (manual)</label>
                            <div className="flex gap-2">
                              <input
                                type="password"
                                value={axetBearerToken}
                                onChange={(e) => setAxetBearerToken(e.target.value)}
                                placeholder={agentConfig?.axet_config?.token_masked || "eyJ..."}
                                className={`${inputCls} flex-1`}
                              />
                              <button
                                onClick={async () => {
                                  if (!axetBearerToken) return;
                                  try {
                                    await fetch(`${API_URL}/api/config/agent/api-key`, {
                                      method: "PUT",
                                      headers: { "Content-Type": "application/json" },
                                      body: JSON.stringify({ provider: "axet", api_key: axetBearerToken }),
                                    });
                                    setAgentSaved(true);
                                    setTimeout(() => setAgentSaved(false), 2000);
                                  } catch {}
                                }}
                                className="px-3 py-2 text-xs font-bold text-white bg-primary rounded-lg hover:bg-primary/90 transition-colors shrink-0"
                              >
                                Aplicar
                              </button>
                            </div>
                            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
                              Alternativa: pega un token manualmente si el login OKTA no esta disponible
                            </p>
                          </div>
                        )}

                        <div>
                          <label className={labelCls}>Proyecto</label>
                          {axetProjects.length > 0 ? (
                            <select
                              value={axetProjectId || agentConfig?.axet_config?.project_id || ""}
                              onChange={(e) => setAxetProjectId(e.target.value)}
                              className={inputCls}
                            >
                              <option value="">Selecciona un proyecto...</option>
                              {axetProjects.map((p) => (
                                <option key={p.id} value={p.id}>{p.displayName || p.id}</option>
                              ))}
                            </select>
                          ) : (
                            <input
                              type="text"
                              value={axetProjectId || agentConfig?.axet_config?.project_id || ""}
                              onChange={(e) => setAxetProjectId(e.target.value)}
                              placeholder={axetAuth?.authenticated ? "Cargando proyectos..." : "Inicia sesion para ver proyectos"}
                              className={inputCls}
                            />
                          )}
                        </div>
                        <p className="text-xs text-slate-400 dark:text-slate-500">Proxy corporativo NTT Data — axet.nttdata.com</p>
                      </>
                    ) : (
                      <div>
                        <label className={labelCls}>Modelo</label>
                        <input type="text" value={agentModel} onChange={(e) => setAgentModel(e.target.value)} className={inputCls} />
                      </div>
                    )}

                    {/* Temperature slider */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className={labelCls}>Temperatura</label>
                        <span className="text-xs font-semibold text-primary">{agentTemp.toFixed(1)} — {tempLabel}</span>
                      </div>
                      <input type="range" min="0" max="1" step="0.1" value={agentTemp}
                        onChange={(e) => setAgentTemp(Number(e.target.value))}
                        className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-full appearance-none cursor-pointer accent-primary [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:shadow-md" />
                      <div className="flex justify-between text-xs text-slate-400 dark:text-slate-500 mt-1">
                        <span>Preciso</span>
                        <span>Creativo</span>
                      </div>
                    </div>
                  </div>

                  {/* Connection test result */}
                  {connectionResult && (
                    <div className={`mt-3 p-3 rounded-lg text-sm font-medium ${
                      connectionResult.success
                        ? "bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800"
                        : "bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800"
                    }`}>
                      {connectionResult.success ? "✓" : "✗"} {connectionResult.message}
                    </div>
                  )}

                  <div className="flex items-center justify-end gap-3 mt-4">
                    {agentSaved && (
                      <span className="text-sm font-medium text-green-600 dark:text-green-400 flex items-center gap-1">
                        <IconCheck /> Guardado
                      </span>
                    )}
                    <button
                      onClick={async () => {
                        setTestingConnection(true);
                        setConnectionResult(null);
                        try {
                          const payload: Record<string, string> = { provider: agentProvider, model: agentModel };
                          if (agentProvider === "openai" && openaiApiKey) payload.api_key = openaiApiKey;
                          if (agentProvider === "axet") {
                            if (axetBearerToken) payload.axet_bearer_token = axetBearerToken;
                            if (axetAssetId) payload.axet_asset_id = axetAssetId;
                            if (axetProjectId) payload.axet_project_id = axetProjectId;
                          }
                          const res = await fetch(`${API_URL}/api/config/agent/test-connection`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify(payload),
                          });
                          const data = await res.json();
                          setConnectionResult({ success: data.success, message: data.message });
                        } catch (e) {
                          setConnectionResult({ success: false, message: "Error de red al probar conexion" });
                        }
                        setTestingConnection(false);
                      }}
                      disabled={testingConnection}
                      className="px-4 py-2 text-sm font-bold rounded-lg border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                    >
                      {testingConnection ? "Probando..." : "Probar Conexion"}
                    </button>
                    <button onClick={handleSaveAgentLLM} disabled={agentSaving} className={btnPrimary}>
                      {agentSaving ? "Guardando..." : "Guardar Configuracion LLM"}
                    </button>
                  </div>
                </section>

                {/* Section 2: System Prompt */}
                <section>
                  <div className="flex items-center justify-between mb-1">
                    <h2 className={h2Cls}>System Prompt</h2>
                    <div className="flex items-center gap-2">
                      {promptModified && (
                        <span className="px-2 py-0.5 text-xs font-bold bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 rounded">MODIFICADO</span>
                      )}
                      <span className="text-xs text-slate-400 dark:text-slate-500">{agentPrompt.length} caracteres</span>
                    </div>
                  </div>
                  <p className={`${descCls} mb-4`}>El prompt del sistema define el comportamiento del agente. Los cambios se aplican inmediatamente.</p>

                  <textarea
                    value={agentPrompt}
                    onChange={(e) => setAgentPrompt(e.target.value)}
                    className={`${inputCls} font-mono text-xs leading-relaxed resize-y`}
                    style={{ minHeight: "400px" }}
                  />

                  <div className="flex items-center justify-between mt-4">
                    <button onClick={handleRestoreDefaultPrompt}
                      className="px-4 py-2 text-sm font-semibold text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
                      Restaurar por defecto
                    </button>
                    <div className="flex items-center gap-3">
                      {promptSaved && (
                        <span className="text-sm font-medium text-green-600 dark:text-green-400 flex items-center gap-1">
                          <IconCheck /> Guardado
                        </span>
                      )}
                      <button onClick={handleSavePrompt} disabled={promptSaving} className={btnPrimary}>
                        {promptSaving ? "Guardando..." : "Guardar Prompt"}
                      </button>
                    </div>
                  </div>
                </section>

                {/* Section 3: Tools */}
                <section>
                  <div className="flex items-center justify-between mb-1">
                    <h2 className={h2Cls}>Herramientas (Tools)</h2>
                    <span className="px-2.5 py-1 text-xs font-bold bg-primary/10 text-primary rounded-full">
                      {activeToolsCount}/{agentTools.length} activas
                    </span>
                  </div>
                  <p className={`${descCls} mb-4`}>Activa o desactiva las herramientas que el agente puede usar. Los cambios se aplican inmediatamente.</p>

                  <div className="grid grid-cols-2 gap-3">
                    {agentTools.map((tool) => (
                      <div key={tool.name}
                        className={`p-4 rounded-xl border transition-all ${
                          tool.enabled
                            ? "border-primary/40 bg-primary/5 dark:bg-primary/10"
                            : "border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50"
                        }`}>
                        <div className="flex items-center justify-between">
                          <div className="flex-1 min-w-0 mr-3">
                            <p className="text-sm font-bold text-slate-900 dark:text-slate-100">{tool.name}</p>
                            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{tool.description}</p>
                          </div>
                          <button
                            onClick={() => handleToggleTool(tool.name, !tool.enabled)}
                            className={`relative w-10 h-5 rounded-full transition-colors shrink-0 ${tool.enabled ? "bg-primary" : "bg-slate-300 dark:bg-slate-600"}`}
                          >
                            <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${tool.enabled ? "left-[22px]" : "left-0.5"}`} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              </div>
            )}

            {/* ===== ANONYMIZATION TAB ===== */}
            {activeTab === "anonymization" && (() => {
              const anonPanels = [
                { id: "regex" as const, label: "Regex", icon: "Rx", desc: "Patrones deterministas", always: false },
                { id: "presidio" as const, label: "Presidio NLP", icon: "AI", desc: "Deteccion con spaCy", always: false },
                { id: "llm" as const, label: "LLM Validador", icon: "\u2728", desc: "Validacion por IA", always: false },
                { id: "output" as const, label: "Sustitucion", icon: "\u2192", desc: "Como se reemplazan", always: true },
              ];
              type AnonPanel = "regex" | "presidio" | "llm" | "output";
              const isRegexActive = detectorType === "regex" || detectorType === "composite";
              const isPresidioActive = detectorType === "presidio" || detectorType === "composite";

              return (
              <div className="space-y-6">
                {/* Intro */}
                <div>
                  <h2 className={h2Cls}>Pipeline de Anonimizacion</h2>
                  <p className={descCls}>Cada capa filtra datos personales. Activa las que necesites — se ejecutan en orden de arriba a abajo.</p>
                </div>

                {/* Accordion panels */}
                <div className="space-y-3">
                  {anonPanels.map((panel, idx) => {
                    const isOpen = anonOpenPanel === panel.id;
                    const layerEnabled = panel.id === "regex" ? isRegexActive
                      : panel.id === "presidio" ? isPresidioActive
                      : panel.id === "llm" ? anonLlmEnabled
                      : true;

                    return (
                      <div key={panel.id} className={`${cardCls} overflow-hidden transition-all`}>
                        {/* Header */}
                        <button type="button" onClick={() => setAnonOpenPanel(isOpen ? null : panel.id)}
                          className="w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-slate-50/50 dark:hover:bg-slate-700/30 transition-colors">
                          {/* Step number */}
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold shrink-0 ${
                            layerEnabled ? "bg-primary text-white" : "bg-slate-200 dark:bg-slate-700 text-slate-400 dark:text-slate-500"
                          }`}>
                            {panel.icon}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <p className="text-sm font-bold text-slate-900 dark:text-slate-100">{panel.label}</p>
                              {panel.always ? (
                                <span className="px-1.5 py-0.5 text-xs font-bold bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400 rounded">ACTIVO</span>
                              ) : layerEnabled ? (
                                <span className="px-1.5 py-0.5 text-xs font-bold bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400 rounded">ON</span>
                              ) : (
                                <span className="px-1.5 py-0.5 text-xs font-bold bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 rounded">OFF</span>
                              )}
                              {idx < 3 && <span className="text-xs text-slate-400 dark:text-slate-500">Capa {idx + 1}</span>}
                            </div>
                            <p className="text-xs text-slate-500 dark:text-slate-400">{panel.desc}</p>
                          </div>
                          <svg className={`w-5 h-5 text-slate-400 transition-transform ${isOpen ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7"/></svg>
                        </button>

                        {/* Collapsible content */}
                        {isOpen && (
                          <div className="px-5 pb-5 border-t border-slate-100 dark:border-slate-700 pt-4 space-y-4">

                            {/* ===== REGEX PANEL ===== */}
                            {panel.id === "regex" && (
                              <>
                                <div className="flex items-center justify-between">
                                  <p className="text-xs text-slate-500 dark:text-slate-400 flex-1">
                                    Detecta patrones estructurados: emails, DNI, IBAN, IPs, telefonos y nombres espanoles.
                                  </p>
                                  <button type="button"
                                    onClick={() => {
                                      if (isRegexActive && isPresidioActive) setDetectorType("presidio");
                                      else if (isRegexActive) setDetectorType("presidio");
                                      else if (isPresidioActive) setDetectorType("composite");
                                      else setDetectorType("regex");
                                    }}
                                    className={`relative w-10 h-5 rounded-full transition-colors shrink-0 ml-4 ${isRegexActive ? "bg-primary" : "bg-slate-300 dark:bg-slate-600"}`}
                                  >
                                    <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${isRegexActive ? "left-[22px]" : "left-0.5"}`} />
                                  </button>
                                </div>

                                {!isRegexActive && (
                                  <p className="text-xs text-slate-400 dark:text-slate-500 italic">Deshabilitado.</p>
                                )}

                                {isRegexActive && (
                                  <>
                                    {/* PII rules */}
                                    <div>
                                      <span className={labelCls}>Patrones detectados</span>
                                      <div className="rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
                                        {PII_RULES_META.map((rule) => (
                                          <div key={rule.id} className="flex items-center justify-between px-4 py-2.5 border-b border-slate-100 dark:border-slate-700 last:border-0 hover:bg-slate-50/50 dark:hover:bg-slate-700/50 transition-colors">
                                            <div className="flex items-center gap-2">
                                              <span className="px-1.5 py-0.5 text-[10px] font-bold bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 rounded uppercase">{rule.category}</span>
                                              <span className="text-sm text-slate-800 dark:text-slate-200">{rule.label}</span>
                                            </div>
                                            <button type="button"
                                              onClick={() => setPiiStates((s) => ({ ...s, [rule.id]: !s[rule.id] }))}
                                              className={`relative w-9 h-[18px] rounded-full transition-colors ${piiStates[rule.id] ? "bg-primary" : "bg-slate-300 dark:bg-slate-600"}`}
                                            >
                                              <span className={`absolute top-[1px] w-4 h-4 bg-white rounded-full shadow transition-transform ${piiStates[rule.id] ? "left-[19px]" : "left-[1px]"}`} />
                                            </button>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  </>
                                )}
                              </>
                            )}

                            {/* ===== PRESIDIO PANEL ===== */}
                            {panel.id === "presidio" && (
                              <>
                                <div className="flex items-center justify-between">
                                  <p className="text-xs text-slate-500 dark:text-slate-400 flex-1">
                                    Microsoft Presidio con spaCy (es_core_news_lg). Detecta nombres, organizaciones y ubicaciones por NLP.
                                  </p>
                                  <button type="button"
                                    onClick={() => {
                                      if (!presidioAvailable) return;
                                      if (isPresidioActive) setDetectorType("regex");
                                      else setDetectorType("composite");
                                    }}
                                    disabled={!presidioAvailable}
                                    className={`relative w-10 h-5 rounded-full transition-colors shrink-0 ml-4 ${!presidioAvailable ? "bg-slate-200 dark:bg-slate-700 cursor-not-allowed" : isPresidioActive ? "bg-primary" : "bg-slate-300 dark:bg-slate-600"}`}
                                  >
                                    <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${isPresidioActive ? "left-[22px]" : "left-0.5"}`} />
                                  </button>
                                </div>

                                {!presidioAvailable ? (
                                  <div className="px-4 py-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                                    <p className="text-xs text-amber-800 dark:text-amber-300 font-medium">Presidio no esta instalado. Para habilitarlo:</p>
                                    <code className="block mt-1 text-xs text-amber-700 dark:text-amber-400 bg-amber-100/50 dark:bg-amber-900/30 px-2 py-1 rounded font-mono">
                                      pip install presidio-analyzer &amp;&amp; python -m spacy download es_core_news_lg
                                    </code>
                                  </div>
                                ) : isPresidioActive ? (
                                  <div className="space-y-4">
                                    {/* Umbral de confianza */}
                                    <div className="bg-slate-50 dark:bg-slate-900/50 rounded-lg p-4">
                                      <div className="flex items-center justify-between mb-2">
                                        <span className={labelCls}>Umbral de confianza NLP</span>
                                        <span className={`text-sm font-bold ${presidioSensitivity < 35 ? "text-green-600" : presidioSensitivity < 70 ? "text-primary" : "text-red-500"}`}>
                                          {presidioSensitivity < 35 ? "CONSERVADOR" : presidioSensitivity < 70 ? "EQUILIBRADO" : "AGRESIVO"} ({presidioSensitivity}%)
                                        </span>
                                      </div>
                                      <input type="range" min="0" max="100" value={presidioSensitivity} onChange={(e) => setPresidioSensitivity(Number(e.target.value))}
                                        className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-full appearance-none cursor-pointer accent-primary [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:shadow-md" />
                                      <div className="flex justify-between mt-1">
                                        <span className="text-xs text-slate-400">Menos detecciones</span>
                                        <span className="text-xs text-slate-400">Mas detecciones</span>
                                      </div>
                                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">
                                        Score minimo de confianza del modelo NLP para reportar una entidad como PII.
                                      </p>
                                    </div>

                                    {/* Entidades NLP */}
                                    <div>
                                      <span className={labelCls}>Entidades detectadas</span>
                                      <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">Tipos de PII que Presidio buscara en el texto.</p>
                                      <div className="rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
                                        {PRESIDIO_ENTITIES_META.map((ent) => (
                                          <div key={ent.id} className="flex items-center justify-between px-4 py-2.5 border-b border-slate-100 dark:border-slate-700 last:border-0 hover:bg-slate-50/50 dark:hover:bg-slate-700/50 transition-colors">
                                            <div className="flex items-center gap-2">
                                              <span className={`px-1.5 py-0.5 text-[10px] font-bold rounded uppercase ${ent.category === "NLP" ? "bg-purple-100 dark:bg-purple-900/40 text-purple-600 dark:text-purple-400" : "bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400"}`}>{ent.category}</span>
                                              <span className="text-sm text-slate-800 dark:text-slate-200">{ent.label}</span>
                                            </div>
                                            <button type="button"
                                              onClick={() => setPresidioEntities((s) => ({ ...s, [ent.id]: !s[ent.id] }))}
                                              className={`relative w-9 h-[18px] rounded-full transition-colors ${presidioEntities[ent.id] ? "bg-primary" : "bg-slate-300 dark:bg-slate-600"}`}
                                            >
                                              <span className={`absolute top-[1px] w-4 h-4 bg-white rounded-full shadow transition-transform ${presidioEntities[ent.id] ? "left-[19px]" : "left-[1px]"}`} />
                                            </button>
                                          </div>
                                        ))}
                                      </div>
                                    </div>

                                    {/* Longitud minima por entidad NER */}
                                    <div>
                                      <span className={labelCls}>Longitud minima por entidad</span>
                                      <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">Textos mas cortos que este limite se descartan como falsos positivos.</p>
                                      <div className="grid grid-cols-3 gap-3">
                                        {(["PERSONA", "UBICACION", "ORGANIZACION"] as const).map((key) => (
                                          <div key={key} className="bg-slate-50 dark:bg-slate-900/50 rounded-lg p-3">
                                            <label className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase">{key}</label>
                                            <input type="number" min="0" max="50" value={presidioMinLengths[key] ?? 0}
                                              onChange={(e) => setPresidioMinLengths((s) => ({ ...s, [key]: Number(e.target.value) }))}
                                              className="w-full mt-1 px-2 py-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded text-sm text-center text-slate-900 dark:text-slate-100 outline-none focus:ring-1 focus:ring-primary" />
                                          </div>
                                        ))}
                                      </div>
                                    </div>

                                    {/* Palabras excluidas (whitelist) */}
                                    <div>
                                      <span className={labelCls}>Palabras excluidas (whitelist)</span>
                                      <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">Palabras que nunca se marcaran como PII aunque Presidio las detecte.</p>
                                      <div className="flex gap-2 mb-2">
                                        <input type="text" value={presidioNewWord}
                                          onChange={(e) => setPresidioNewWord(e.target.value)}
                                          onKeyDown={(e) => {
                                            if (e.key === "Enter" && presidioNewWord.trim()) {
                                              e.preventDefault();
                                              const w = presidioNewWord.trim().toLowerCase();
                                              if (!presidioExcludedWords.includes(w)) {
                                                setPresidioExcludedWords([...presidioExcludedWords, w]);
                                              }
                                              setPresidioNewWord("");
                                            }
                                          }}
                                          placeholder="Escribe una palabra y pulsa Enter"
                                          className={inputCls} />
                                        <button type="button"
                                          onClick={() => {
                                            const w = presidioNewWord.trim().toLowerCase();
                                            if (w && !presidioExcludedWords.includes(w)) {
                                              setPresidioExcludedWords([...presidioExcludedWords, w]);
                                            }
                                            setPresidioNewWord("");
                                          }}
                                          className="px-3 py-2 bg-primary text-white text-xs font-bold rounded-lg hover:bg-blue-600 transition-colors shrink-0">
                                          Anadir
                                        </button>
                                      </div>
                                      {presidioExcludedWords.length > 0 && (
                                        <div className="flex flex-wrap gap-1.5">
                                          {presidioExcludedWords.map((w) => (
                                            <span key={w} className="inline-flex items-center gap-1 px-2 py-1 bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 text-xs rounded-full border border-amber-200 dark:border-amber-800">
                                              {w}
                                              <button type="button"
                                                onClick={() => setPresidioExcludedWords(presidioExcludedWords.filter((x) => x !== w))}
                                                className="text-amber-500 hover:text-red-500 transition-colors font-bold ml-0.5">
                                                x
                                              </button>
                                            </span>
                                          ))}
                                        </div>
                                      )}
                                    </div>

                                    {/* Modelo spaCy */}
                                    <div>
                                      <span className={labelCls}>Modelo spaCy</span>
                                      <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">Modelo de lenguaje para NER. Los modelos mas grandes son mas precisos pero mas lentos.</p>
                                      <div className="grid grid-cols-3 gap-2">
                                        {([
                                          { id: "es_core_news_sm", label: "Small", desc: "Rapido, menos preciso", size: "~12MB" },
                                          { id: "es_core_news_md", label: "Medium", desc: "Equilibrado", size: "~40MB" },
                                          { id: "es_core_news_lg", label: "Large", desc: "Mas preciso, mas lento", size: "~400MB" },
                                        ]).map((m) => (
                                          <button key={m.id} type="button"
                                            onClick={() => setPresidioModel(m.id)}
                                            className={`p-3 rounded-lg border-2 text-left transition-all ${presidioModel === m.id ? "border-primary bg-primary/5 dark:bg-primary/10" : "border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600"}`}>
                                            <span className={`text-sm font-bold ${presidioModel === m.id ? "text-primary" : "text-slate-700 dark:text-slate-300"}`}>{m.label}</span>
                                            <span className="block text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">{m.desc}</span>
                                            <span className="block text-[10px] text-slate-400 dark:text-slate-500">{m.size}</span>
                                          </button>
                                        ))}
                                      </div>
                                      <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-1 italic">Requiere: python -m spacy download {presidioModel}</p>
                                    </div>

                                    {/* Status badge */}
                                    <div className="flex items-center gap-2">
                                      <span className="px-2 py-0.5 text-xs font-bold bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400 rounded">
                                        {activeDetector === "composite" ? "COMPUESTO" : "PRESIDIO"} ACTIVO
                                      </span>
                                    </div>
                                  </div>
                                ) : (
                                  <p className="text-xs text-slate-400 dark:text-slate-500 italic">Deshabilitado. Solo se usa deteccion Regex.</p>
                                )}
                              </>
                            )}

                            {/* ===== LLM PANEL ===== */}
                            {panel.id === "llm" && (
                              <>
                                <div className="flex items-center justify-between">
                                  <p className="text-xs text-slate-500 dark:text-slate-400 flex-1">
                                    LLM dedicado a validar PII en pre/post filtrado. Capa opcional adicional a Regex/Presidio.
                                  </p>
                                  <button type="button"
                                    onClick={() => setAnonLlmEnabled(!anonLlmEnabled)}
                                    className={`relative w-10 h-5 rounded-full transition-colors shrink-0 ml-4 ${anonLlmEnabled ? "bg-primary" : "bg-slate-300 dark:bg-slate-600"}`}
                                  >
                                    <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${anonLlmEnabled ? "left-[22px]" : "left-0.5"}`} />
                                  </button>
                                </div>

                                {anonLlmEnabled ? (
                                  <div className="space-y-4">
                                    {/* Provider */}
                                    <div className="grid grid-cols-2 gap-3">
                                      {[
                                        { id: "openai", title: "OpenAI", desc: "GPT-4o mini", bgColor: "bg-slate-800 dark:bg-slate-600" },
                                        { id: "axet", title: "Axet NTT", desc: "Proxy corporativo", bgColor: "bg-purple-600" },
                                      ].map((p) => (
                                        <button key={p.id} type="button" onClick={() => {
                                          setAnonLlmProvider(p.id);
                                          setAnonLlmTestResult(null);
                                          if (p.id === "openai") setAnonLlmModel(agentConfig?.openai_config?.model || "gpt-4o-mini");
                                          else if (p.id === "axet") {
                                            setAnonLlmModel(agentConfig?.axet_config?.model || "gpt-4o-mini");
                                            if (axetModels.length === 0) { fetchAxetAuthStatus(); fetchAxetModels(); }
                                          }
                                        }}
                                          className={`p-3 rounded-xl border text-left transition-all ${
                                            anonLlmProvider === p.id
                                              ? "border-primary bg-primary/5 dark:bg-primary/10 shadow-sm"
                                              : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:border-slate-300 dark:hover:border-slate-600"
                                          }`}>
                                          <div className="flex items-center gap-3">
                                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold ${p.bgColor}`}>
                                              {p.id.slice(0, 2).toUpperCase()}
                                            </div>
                                            <div className="flex-1 min-w-0">
                                              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{p.title}</p>
                                              <p className="text-xs text-slate-500 dark:text-slate-400">{p.desc}</p>
                                            </div>
                                            <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 ${
                                              anonLlmProvider === p.id ? "border-primary bg-primary" : "border-slate-300 dark:border-slate-600"
                                            }`}>
                                              {anonLlmProvider === p.id && <IconCheck />}
                                            </div>
                                          </div>
                                        </button>
                                      ))}
                                    </div>

                                    {/* Model + config */}
                                    <div className="bg-slate-50 dark:bg-slate-900/50 rounded-lg p-4 space-y-4">
                                      {anonLlmProvider === "openai" ? (
                                        <div className="space-y-3">
                                          <div>
                                            <span className={labelCls}>API Key</span>
                                            <input type="password" value={anonLlmApiKey} onChange={(e) => setAnonLlmApiKey(e.target.value)}
                                              placeholder="sk-..." className={inputCls} />
                                            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">Clave propia para el validador PII. Independiente de la del Agente.</p>
                                          </div>
                                          <span className={labelCls}>Modelo</span>
                                          <select value={anonLlmModel} onChange={(e) => setAnonLlmModel(e.target.value)} className={inputCls}>
                                            {(agentConfig?.openai_config?.available_models || ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]).map((m: string) => (
                                              <option key={m} value={m}>{m}</option>
                                            ))}
                                          </select>
                                          <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">Se recomienda gpt-4o-mini (rapido y economico).</p>
                                        </div>
                                      ) : anonLlmProvider === "axet" ? (
                                        <div className="space-y-3">
                                          {/* Okta inline status */}
                                          <div className={`p-3 rounded-lg border ${
                                            axetAuth?.authenticated
                                              ? "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800"
                                              : axetDeviceCode
                                                ? "bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800"
                                                : "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700"
                                          }`}>
                                            {axetAuth?.authenticated ? (
                                              <div className="flex items-center gap-2">
                                                <div className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse" />
                                                <span className="text-xs font-semibold text-slate-900 dark:text-slate-100">
                                                  {axetAuth.user?.displayName || axetAuth.user?.name || "Autenticado"}
                                                </span>
                                                <span className="text-xs text-slate-400">({Math.floor((axetAuth.expires_in || 0) / 60)} min)</span>
                                              </div>
                                            ) : axetDeviceCode ? (
                                              <div className="text-center space-y-2">
                                                <p className="text-xs text-slate-600 dark:text-slate-300">Introduce el codigo en OKTA:</p>
                                                <p className="text-xl font-mono font-bold tracking-widest text-purple-700 dark:text-purple-400">{axetDeviceCode.user_code}</p>
                                                <a href={axetDeviceCode.verification_uri_complete} target="_blank" rel="noopener noreferrer"
                                                  className="inline-block px-3 py-1.5 text-xs font-bold text-white bg-purple-600 rounded-lg hover:bg-purple-700 transition-colors">
                                                  Abrir OKTA
                                                </a>
                                                <div className="flex items-center justify-center gap-1.5 text-xs text-slate-400">
                                                  <div className="w-2.5 h-2.5 border-2 border-purple-400 border-t-transparent rounded-full animate-spin" />
                                                  Esperando...
                                                </div>
                                                <button type="button" onClick={() => { setAxetDeviceCode(null); setAxetPolling(false); }}
                                                  className="text-xs text-slate-400 hover:text-slate-600">Cancelar</button>
                                              </div>
                                            ) : (
                                              <div className="flex items-center justify-between">
                                                <span className="text-xs text-slate-500">No autenticado en Axet</span>
                                                <button type="button" disabled={axetAuthLoading}
                                                  onClick={async () => {
                                                    setAxetAuthLoading(true);
                                                    try {
                                                      const res = await fetch(`${API_URL}/api/axet/auth/start`, { method: "POST" });
                                                      const data = await res.json();
                                                      if (data.user_code) {
                                                        setAxetDeviceCode({ user_code: data.user_code, verification_uri_complete: data.verification_uri_complete });
                                                        setAxetPolling(true);
                                                        const pollInterval = setInterval(async () => {
                                                          try {
                                                            const pollRes = await fetch(`${API_URL}/api/axet/auth/poll`, { method: "POST" });
                                                            const pollData = await pollRes.json();
                                                            if (pollData.status === "success") { clearInterval(pollInterval); setAxetDeviceCode(null); setAxetPolling(false); fetchAxetAuthStatus(); }
                                                            else if (pollData.status === "expired" || pollData.status === "error") { clearInterval(pollInterval); setAxetDeviceCode(null); setAxetPolling(false); }
                                                          } catch { clearInterval(pollInterval); setAxetDeviceCode(null); setAxetPolling(false); }
                                                        }, 5000);
                                                      }
                                                    } catch {}
                                                    setAxetAuthLoading(false);
                                                  }}
                                                  className="px-3 py-1.5 text-xs font-bold text-white bg-purple-600 rounded-lg hover:bg-purple-700 disabled:opacity-50"
                                                >
                                                  {axetAuthLoading ? "..." : "Login OKTA"}
                                                </button>
                                              </div>
                                            )}
                                          </div>
                                          {axetAuth?.authenticated && (
                                            <div>
                                              <span className={labelCls}>Modelo</span>
                                              {axetModels.length > 0 ? (
                                                <select value={anonLlmModel} onChange={(e) => setAnonLlmModel(e.target.value)} className={inputCls}>
                                                  {axetModels.map((m) => (
                                                    <option key={m.id} value={m.id}>{m.displayName || m.id}</option>
                                                  ))}
                                                </select>
                                              ) : (
                                                <input type="text" value={anonLlmModel} onChange={(e) => setAnonLlmModel(e.target.value)} placeholder="nombre-modelo" className={inputCls} />
                                              )}
                                            </div>
                                          )}
                                        </div>
                                      ) : null}

                                      {/* Temperature */}
                                      <div>
                                        <span className={labelCls}>Temperatura: {(anonLlmTemp ?? 0).toFixed(1)}</span>
                                        <input type="range" min="0" max="1" step="0.1" value={anonLlmTemp || 0}
                                          onChange={(e) => setAnonLlmTemp(Number(e.target.value))}
                                          className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-full appearance-none cursor-pointer accent-primary [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:shadow-md" />
                                        <p className="text-xs text-slate-400 mt-1">0.0 recomendado (determinista).</p>
                                      </div>
                                    </div>

                                    {/* Test result */}
                                    {anonLlmTestResult && (
                                      <div className={`px-4 py-2.5 rounded-lg text-xs font-medium ${
                                        anonLlmTestResult.success
                                          ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800"
                                          : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800"
                                      }`}>
                                        {anonLlmTestResult.message}
                                      </div>
                                    )}

                                    {/* System Prompt */}
                                    <div>
                                      <div className="flex items-center justify-between mb-1">
                                        <span className={labelCls}>Prompt del validador</span>
                                        {anonLlmPrompt !== anonLlmDefaultPrompt && (
                                          <button type="button" onClick={() => setAnonLlmPrompt(anonLlmDefaultPrompt)}
                                            className="text-[10px] text-primary hover:underline">Restaurar default</button>
                                        )}
                                      </div>
                                      <textarea value={anonLlmPrompt} onChange={(e) => setAnonLlmPrompt(e.target.value)}
                                        rows={8}
                                        className={`${inputCls} font-mono text-xs leading-relaxed resize-y`}
                                        placeholder="Prompt del sistema para el validador PII..." />
                                      <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-1">
                                        Instrucciones que recibe el LLM para detectar PII no capturado por regex/Presidio.
                                      </p>
                                    </div>

                                    {/* Actions */}
                                    <div className="flex items-center justify-end gap-2">
                                      <button type="button" onClick={handleTestAnonLlm} disabled={anonLlmTesting || !anonLlmModel}
                                        className="px-3 py-1.5 text-xs font-semibold text-primary border border-primary/30 rounded-lg hover:bg-primary/5 transition-colors disabled:opacity-50">
                                        {anonLlmTesting ? "Probando..." : "Probar conexion"}
                                      </button>
                                      {anonLlmSaved && <span className="text-xs font-medium text-green-600 dark:text-green-400 flex items-center gap-1"><IconCheck /> OK</span>}
                                      <button type="button" onClick={handleSaveAnonLlm} disabled={anonLlmSaving} className={btnPrimary}>
                                        {anonLlmSaving ? "..." : "Guardar"}
                                      </button>
                                    </div>
                                  </div>
                                ) : (
                                  <p className="text-xs text-slate-400 dark:text-slate-500 italic">Deshabilitado. Solo se usa Regex/Presidio.</p>
                                )}
                              </>
                            )}

                            {/* ===== SUBSTITUTION PANEL ===== */}
                            {panel.id === "output" && (
                              <>
                                <p className="text-xs text-slate-500 dark:text-slate-400">
                                  Como se reemplazan los datos personales detectados por las capas anteriores.
                                </p>
                                <div className="space-y-2">
                                  {[
                                    { id: "redacted", title: "Redaccion total [REDACTED]", desc: "Mascarado estatico sin contexto." },
                                    { id: "synthetic", title: "Sustitucion sintetica [PERSONA_1]", desc: "Tokens tipo-entidad. Recomendado para soporte." },
                                    { id: "aes256", title: "Cifrado reversible AES-256", desc: "Permite recuperacion autorizada de datos originales." },
                                  ].map((opt) => (
                                    <button key={opt.id} type="button" onClick={() => setSubstitutionTechnique(opt.id)}
                                      className={`w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all ${
                                        substitutionTechnique === opt.id
                                          ? "border-primary bg-primary/5 dark:bg-primary/10"
                                          : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:border-slate-300 dark:hover:border-slate-600"
                                      }`}>
                                      <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 ${
                                        substitutionTechnique === opt.id ? "border-primary bg-primary" : "border-slate-300 dark:border-slate-600"
                                      }`}>
                                        {substitutionTechnique === opt.id && <IconCheck />}
                                      </div>
                                      <div>
                                        <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{opt.title}</p>
                                        <p className="text-xs text-slate-500 dark:text-slate-400">{opt.desc}</p>
                                      </div>
                                    </button>
                                  ))}
                                </div>
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Global save */}
                <div className="flex items-center justify-end gap-3">
                  {anonSaved && (
                    <span className="text-sm font-medium text-green-600 dark:text-green-400 flex items-center gap-1">
                      <IconCheck /> Guardado
                    </span>
                  )}
                  <button type="button" onClick={handleSaveAnonymization} disabled={anonSaving} className={btnPrimary}>
                    {anonSaving ? "Guardando..." : "Guardar configuracion"}
                  </button>
                </div>
              </div>
              );
            })()}

            {/* ===== INTEGRATIONS TAB ===== */}
            {activeTab === "integrations" && (() => {
              const sourceIntegrations = integrations.filter(s => s.system_type === "source" || s.system_type === "both");
              const destIntegrations = integrations.filter(s => s.system_type === "both" || s.system_type === "destination");

              const renderIntegrationCard = (sys: IntegrationConfig, badge: { label: string; color: string }) => (
                <div key={sys.system_name + badge.label} className={cardCls + " overflow-hidden"}>
                  <div className="p-5 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-white text-sm font-bold ${systemBgColor(sys.system_name)}`}>
                        {sys.display_name.slice(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-bold text-slate-900 dark:text-slate-100">{sys.display_name}</p>
                          <span className={`px-1.5 py-0.5 text-xs font-bold rounded ${badge.color}`}>{badge.label}</span>
                          <span className={`w-2 h-2 rounded-full ${statusDot(sys.last_connection_status)}`} />
                          {!sys.is_active && <span className="px-1.5 py-0.5 text-xs font-bold bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 rounded">INACTIVO</span>}
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          {timeAgo(sys.last_connection_test)} · {sys.connector_type.toUpperCase()}
                          {sys.base_url ? ` · ${sys.base_url.replace(/https?:\/\//, "").split("/")[0]}` : ""}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleTest(sys.system_name)}
                        disabled={testingSystem === sys.system_name}
                        className="px-3 py-1.5 text-xs font-semibold text-primary border border-primary/30 rounded-lg hover:bg-primary/5 transition-colors disabled:opacity-50"
                      >
                        {testingSystem === sys.system_name ? (
                          <span className="flex items-center gap-1.5">
                            <svg className="animate-spin w-3 h-3" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                            Probando...
                          </span>
                        ) : "Probar Conexion"}
                      </button>
                      <button
                        onClick={() => handleExpand(sys.system_name)}
                        className="px-3 py-1.5 text-xs font-semibold text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                      >
                        {expandedSystem === sys.system_name ? "Cerrar" : "Gestionar"}
                      </button>
                      {confirmDeleteIntegration === sys.system_name ? (
                        <div className="flex items-center gap-1">
                          <button onClick={() => handleDeleteIntegration(sys.system_name)}
                            disabled={deletingIntegration === sys.system_name}
                            className="px-2 py-1.5 text-xs font-semibold text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50">
                            {deletingIntegration === sys.system_name ? "..." : "Eliminar"}
                          </button>
                          <button onClick={() => setConfirmDeleteIntegration(null)}
                            className="px-2 py-1.5 text-xs font-semibold text-slate-500 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700">
                            No
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setConfirmDeleteIntegration(sys.system_name)}
                          className="p-1.5 text-xs text-red-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                          title="Eliminar integracion"
                        >
                          <IconTrash />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Test result */}
                  {testResult[sys.system_name] && (
                    <div className={`mx-5 mb-3 px-3 py-2 rounded-lg text-xs font-medium ${
                      testResult[sys.system_name].status === "connected"
                        ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800"
                        : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800"
                    }`}>
                      {testResult[sys.system_name].message}
                    </div>
                  )}

                  {/* Expanded edit panel */}
                  {expandedSystem === sys.system_name && (
                    <div className="border-t border-slate-200 dark:border-slate-700 p-5 bg-slate-50/50 dark:bg-slate-900/50 space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className={labelCls}>URL Base</label>
                          <input type="text" value={String(editForm.base_url || "")}
                            onChange={(e) => setEditForm((f) => ({ ...f, base_url: e.target.value }))}
                            placeholder="https://..." className={inputCls} />
                        </div>
                        <div>
                          <label className={labelCls}>Token (dejar vacio para mantener actual)</label>
                          <input type="password" value={String(editForm.auth_token || "")}
                            onChange={(e) => setEditForm((f) => ({ ...f, auth_token: e.target.value }))}
                            placeholder={sys.auth_token_masked} className={inputCls} />
                        </div>
                        <div>
                          <label className={labelCls}>Email</label>
                          <input type="email" value={String(editForm.auth_email || "")}
                            onChange={(e) => setEditForm((f) => ({ ...f, auth_email: e.target.value }))}
                            className={inputCls} />
                        </div>
                        <div>
                          <label className={labelCls}>Proyecto</label>
                          <input type="text" value={String(editForm.project_key || "")}
                            onChange={(e) => setEditForm((f) => ({ ...f, project_key: e.target.value }))}
                            className={inputCls} />
                        </div>
                      </div>

                      {sys.connector_type === "jira" && (
                        <div className="grid grid-cols-3 gap-4">
                          <div>
                            <label className={labelCls}>Board ID</label>
                            <input type="text" value={String(editForm.board_id || "")}
                              onChange={(e) => setEditForm((f) => ({ ...f, board_id: e.target.value }))}
                              className={inputCls} />
                          </div>
                          <div>
                            <label className={labelCls}>Issue Type ID</label>
                            <input type="text" value={String(editForm.issue_type_id || "")}
                              onChange={(e) => setEditForm((f) => ({ ...f, issue_type_id: e.target.value }))}
                              className={inputCls} />
                          </div>
                          <div>
                            <label className={labelCls}>Parent Key</label>
                            <input type="text" value={String(editForm.parent_key || "")}
                              onChange={(e) => setEditForm((f) => ({ ...f, parent_key: e.target.value }))}
                              className={inputCls} />
                          </div>
                        </div>
                      )}

                      <div className="grid grid-cols-3 gap-4">
                        <div>
                          <label className={labelCls}>Polling (seg)</label>
                          <input type="number" min={5}
                            value={Number(editForm.polling_interval_sec || 60)}
                            onChange={(e) => setEditForm((f) => ({ ...f, polling_interval_sec: Number(e.target.value) }))}
                            className={inputCls} />
                        </div>
                        <div className="flex items-end gap-4">
                          <label className="flex items-center gap-2 cursor-pointer">
                            <button onClick={() => setEditForm((f) => ({ ...f, is_active: !f.is_active }))}
                              className={`relative w-10 h-5 rounded-full transition-colors ${editForm.is_active ? "bg-primary" : "bg-slate-300 dark:bg-slate-600"}`}>
                              <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${editForm.is_active ? "left-[22px]" : "left-0.5"}`} />
                            </button>
                            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">Activo</span>
                          </label>
                        </div>
                      </div>

                      <div className="flex justify-end gap-2 pt-2">
                        <button onClick={() => setExpandedSystem(null)}
                          className="px-4 py-2 text-sm font-semibold text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-white dark:hover:bg-slate-700 transition-colors">
                          Cancelar
                        </button>
                        <button onClick={() => handleSave(sys.system_name)} disabled={saving} className={btnPrimary}>
                          {saving ? "Guardando..." : "Guardar"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );

              return (
              <div className="space-y-8">
                {/* --- Sistemas Origen --- */}
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                      <svg className="w-5 h-5 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                      </svg>
                    </div>
                    <div>
                      <h2 className={h2Cls}>Sistemas Origen</h2>
                      <p className={descCls}>Sistemas de ticketing de los que se leen incidencias para anonimizar.</p>
                    </div>
                  </div>
                  <div className="space-y-3">
                    {sourceIntegrations.length > 0 ? sourceIntegrations.map((sys) =>
                      renderIntegrationCard(sys, { label: "ORIGEN", color: "bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300" })
                    ) : (
                      <div className={`${cardCls} p-10 text-center`}>
                        <p className={descCls}>No hay sistemas origen configurados</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* --- Sistemas Destino --- */}
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                      <svg className="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12M12 16.5V3" />
                      </svg>
                    </div>
                    <div>
                      <h2 className={h2Cls}>Sistemas Destino</h2>
                      <p className={descCls}>Sistemas donde se crean las copias anonimizadas de los tickets.</p>
                    </div>
                  </div>
                  <div className="space-y-3">
                    {destIntegrations.length > 0 ? destIntegrations.map((sys) =>
                      renderIntegrationCard(sys, { label: "DESTINO", color: "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300" })
                    ) : (
                      <div className={`${cardCls} p-10 text-center`}>
                        <p className={descCls}>No hay sistemas destino configurados</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* --- Añadir integracion --- */}
                {!showAddForm ? (
                  <button onClick={() => setShowAddForm(true)}
                    className="w-full py-3 border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-xl text-sm font-semibold text-slate-500 dark:text-slate-400 hover:border-primary hover:text-primary transition-colors">
                    + Añadir integracion
                  </button>
                ) : (
                  <div className={cardCls + " p-5 space-y-4"}>
                    <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Nueva integracion</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className={labelCls}>Identificador (sin espacios)</label>
                        <input type="text" value={newIntegration.system_name} placeholder="mi-jira-prod"
                          onChange={(e) => setNewIntegration(p => ({ ...p, system_name: e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, "") }))}
                          className={inputCls} />
                      </div>
                      <div>
                        <label className={labelCls}>Nombre visible</label>
                        <input type="text" value={newIntegration.display_name} placeholder="Jira Produccion"
                          onChange={(e) => setNewIntegration(p => ({ ...p, display_name: e.target.value }))}
                          className={inputCls} />
                      </div>
                      <div>
                        <label className={labelCls}>Tipo de sistema</label>
                        <select value={newIntegration.system_type}
                          onChange={(e) => setNewIntegration(p => ({ ...p, system_type: e.target.value }))}
                          className={inputCls}>
                          <option value="source">Origen</option>
                          <option value="destination">Destino</option>
                        </select>
                      </div>
                      <div>
                        <label className={labelCls}>Tipo de conector</label>
                        <select value={newIntegration.connector_type}
                          onChange={(e) => setNewIntegration(p => ({ ...p, connector_type: e.target.value }))}
                          className={inputCls}>
                          <option value="jira">Jira</option>
                          <option value="remedy">Remedy</option>
                          <option value="servicenow">ServiceNow</option>
                        </select>
                      </div>
                      <div>
                        <label className={labelCls}>URL Base</label>
                        <input type="text" value={newIntegration.base_url} placeholder="https://jira.example.com"
                          onChange={(e) => setNewIntegration(p => ({ ...p, base_url: e.target.value }))}
                          className={inputCls} />
                      </div>
                      <div>
                        <label className={labelCls}>Proyecto</label>
                        <input type="text" value={newIntegration.project_key} placeholder="MYPROJECT"
                          onChange={(e) => setNewIntegration(p => ({ ...p, project_key: e.target.value }))}
                          className={inputCls} />
                      </div>
                      <div>
                        <label className={labelCls}>Token</label>
                        <input type="password" value={newIntegration.auth_token} placeholder="Bearer token"
                          onChange={(e) => setNewIntegration(p => ({ ...p, auth_token: e.target.value }))}
                          className={inputCls} />
                      </div>
                      <div>
                        <label className={labelCls}>Email</label>
                        <input type="email" value={newIntegration.auth_email} placeholder="usuario@empresa.com"
                          onChange={(e) => setNewIntegration(p => ({ ...p, auth_email: e.target.value }))}
                          className={inputCls} />
                      </div>
                    </div>
                    <div className="flex justify-end gap-2 pt-2">
                      <button onClick={() => setShowAddForm(false)}
                        className="px-4 py-2 text-sm font-semibold text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-white dark:hover:bg-slate-700 transition-colors">
                        Cancelar
                      </button>
                      <button onClick={handleAddIntegration} disabled={addingIntegration || !newIntegration.system_name || !newIntegration.display_name} className={btnPrimary}>
                        {addingIntegration ? "Creando..." : "Crear integracion"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
              );
            })()}

            {/* ===== TICKETS TAB ===== */}
            {activeTab === "tickets" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className={h2Cls}>Gestion de Tickets</h2>
                    <p className={descCls}>Administra los tickets ingestados. Puedes eliminar tickets y sus datos asociados.</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-500 dark:text-slate-400">{adminTickets.length} ticket{adminTickets.length !== 1 ? "s" : ""}</span>
                    <button onClick={fetchAdminTickets} className="p-2 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors" title="Refrescar">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                      </svg>
                    </button>
                  </div>
                </div>
                {adminLoading ? (
                  <div className="text-center py-20">
                    <div className="w-10 h-10 mx-auto border-[3px] border-primary/20 border-t-primary rounded-full animate-spin mb-4" />
                    <p className={descCls}>Cargando tickets...</p>
                  </div>
                ) : adminTickets.length === 0 ? (
                  <div className={`${cardCls} text-center py-16`}>
                    <div className="w-14 h-14 mx-auto mb-4 bg-primary/5 rounded-2xl flex items-center justify-center border border-primary/10">
                      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-primary">
                        <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
                      </svg>
                    </div>
                    <p className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-1">No hay tickets ingestados</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">Los tickets apareceran aqui una vez ingestados desde la vista de Incidencias</p>
                  </div>
                ) : (
                  <div className={`${cardCls} overflow-hidden`}>
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800">
                          <th className="text-left px-4 py-3 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">KOSIN Key</th>
                          <th className="text-left px-4 py-3 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Origen</th>
                          <th className="text-left px-4 py-3 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Source Key</th>
                          <th className="text-left px-4 py-3 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Resumen</th>
                          <th className="text-left px-4 py-3 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Prioridad</th>
                          <th className="text-left px-4 py-3 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Estado</th>
                          <th className="text-left px-4 py-3 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Creado</th>
                          <th className="text-right px-4 py-3 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Accion</th>
                        </tr>
                      </thead>
                      <tbody>
                        {adminTickets.map((t) => {
                          const pr = priorityConfig[t.priority] || { bg: "bg-slate-100 dark:bg-slate-700", text: "text-slate-600 dark:text-slate-300", label: t.priority };
                          const st = statusConfig[t.status] || { bg: "bg-slate-100 dark:bg-slate-700", text: "text-slate-600 dark:text-slate-300", label: t.status };
                          return (
                            <tr key={t.id} className="border-b border-slate-100 dark:border-slate-700 hover:bg-slate-50/50 dark:hover:bg-slate-800/50 transition-colors">
                              <td className="px-4 py-3 text-sm font-semibold">
                                <a href={`/?ticket=${t.id}`} className="text-primary hover:underline">{t.kosin_ticket_id}</a>
                              </td>
                              <td className="px-4 py-3">
                                <span className="px-2 py-0.5 text-xs font-bold bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 rounded uppercase">{t.source_system}</span>
                              </td>
                              <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400">{t.source_ticket_id}</td>
                              <td className="px-4 py-3 text-sm text-slate-800 dark:text-slate-200 max-w-[300px] truncate">{t.summary}</td>
                              <td className="px-4 py-3">
                                <span className={`px-2 py-0.5 text-xs font-bold rounded-full ${pr.bg} ${pr.text}`}>{pr.label}</span>
                              </td>
                              <td className="px-4 py-3">
                                <span className={`px-2 py-0.5 text-xs font-bold rounded-full ${st.bg} ${st.text}`}>{st.label}</span>
                              </td>
                              <td className="px-4 py-3 text-xs text-slate-500 dark:text-slate-400">{new Date(t.created_at).toLocaleDateString("es-ES")}</td>
                              <td className="px-4 py-3 text-right">
                                <button onClick={() => setConfirmDelete(t.kosin_ticket_id)}
                                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors">
                                  <IconTrash />
                                  Eliminar
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        </main>
      </div>

      {/* Delete confirmation modal */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className={`${cardCls} shadow-2xl p-6 max-w-sm w-full mx-4`}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center shrink-0">
                <IconTrash />
              </div>
              <div>
                <p className="text-sm font-bold text-slate-900 dark:text-slate-100">Eliminar ticket</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">Esta accion no se puede deshacer</p>
              </div>
            </div>
            <p className="text-sm text-slate-700 dark:text-slate-300 mb-1">
              Se eliminara <span className="font-semibold text-primary">{confirmDelete}</span> de KOSIN y de la base de datos, incluyendo historial de chat y mapa de sustitucion.
            </p>
            {deleteError && (
              <div className="mt-3 px-3 py-2 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 text-xs font-medium rounded-lg border border-red-200 dark:border-red-800">
                {deleteError}
              </div>
            )}
            <div className="flex justify-end gap-2 mt-5">
              <button
                onClick={() => { setConfirmDelete(null); setDeleteError(null); }}
                className="px-4 py-2 text-sm font-semibold text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={() => handleDeleteTicket(confirmDelete)}
                disabled={deleting === confirmDelete}
                className="px-4 py-2 text-sm font-bold text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {deleting === confirmDelete ? "Eliminando..." : "Eliminar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
