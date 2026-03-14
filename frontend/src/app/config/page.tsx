"use client";

import { useState, useEffect, useCallback } from "react";
import type { IntegrationConfig } from "@/types";
import { Header } from "@/components/Header";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Tab = "general" | "anonymization" | "integrations" | "tickets";

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
  { id: "integrations", label: "Integraciones", icon: <IconPlug /> },
  { id: "tickets", label: "Tickets", icon: <IconDatabase /> },
];

const piiRules = [
  { id: "names", label: "Nombres y Apellidos", enabled: true, category: "Personal" },
  { id: "emails", label: "Emails", enabled: true, category: "Personal" },
  { id: "phones", label: "Telefonos", enabled: true, category: "Personal" },
  { id: "ips", label: "Direcciones IP", enabled: true, category: "Tecnico" },
  { id: "cards", label: "Numeros de Tarjeta/Cuenta", enabled: true, category: "Financiero" },
  { id: "addresses", label: "Direcciones postales", enabled: false, category: "Personal" },
];

const priorityConfig: Record<string, { bg: string; text: string; label: string }> = {
  critical: { bg: "bg-red-100", text: "text-red-700", label: "Critica" },
  high: { bg: "bg-amber-100", text: "text-amber-700", label: "Alta" },
  medium: { bg: "bg-blue-100", text: "text-blue-700", label: "Media" },
  low: { bg: "bg-green-100", text: "text-green-700", label: "Baja" },
};

const statusConfig: Record<string, { bg: string; text: string; label: string }> = {
  open: { bg: "bg-blue-100", text: "text-blue-700", label: "Abierto" },
  in_progress: { bg: "bg-emerald-100", text: "text-emerald-700", label: "En progreso" },
  resolved: { bg: "bg-slate-100", text: "text-slate-600", label: "Resuelto" },
  closed: { bg: "bg-slate-100", text: "text-slate-500", label: "Cerrado" },
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

export default function ConfigPage() {
  const [activeTab, setActiveTab] = useState<Tab>("integrations");
  const [substitutionTechnique, setSubstitutionTechnique] = useState("synthetic");
  const [sensitivity, setSensitivity] = useState(65);
  const [piiStates, setPiiStates] = useState<Record<string, boolean>>(
    Object.fromEntries(piiRules.map((r) => [r.id, r.enabled]))
  );

  // Integrations state
  const [integrations, setIntegrations] = useState<IntegrationConfig[]>([]);
  const [expandedSystem, setExpandedSystem] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Record<string, string | number | boolean>>({});
  const [testingSystem, setTestingSystem] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<Record<string, { status: string; message: string }>>({});
  const [saving, setSaving] = useState(false);

  // General settings state
  const [pollingInterval, setPollingInterval] = useState(60);
  const [generalLoaded, setGeneralLoaded] = useState(false);

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
        setGeneralLoaded(true);
      }
    } catch (err) {
      console.error("Failed to fetch general settings:", err);
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

  useEffect(() => {
    fetchIntegrations();
    fetchGeneralSettings();
    fetchAdminTickets();
  }, [fetchIntegrations, fetchGeneralSettings, fetchAdminTickets]);

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
        is_mock: sys.is_mock,
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
      body.is_mock = editForm.is_mock;
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

  const sensitivityLabel = sensitivity < 35 ? "CONSERVADOR" : sensitivity < 70 ? "EQUILIBRADO" : "AGRESIVO";
  const sensitivityColor = sensitivity < 35 ? "text-green-600" : sensitivity < 70 ? "text-primary" : "text-red-500";

  return (
    <div className="bg-[#F8FAFC] text-slate-900 min-h-screen flex flex-col">
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
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <aside className="w-64 bg-white border-r border-slate-200 p-4 shrink-0">
          <div className="space-y-1">
            {tabs.map((tab) => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? "bg-primary/10 text-primary border-r-2 border-primary"
                    : "text-slate-600 hover:bg-slate-50"
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
            {activeTab === "anonymization" && (
              <div className="space-y-8">
                {/* PII Rules */}
                <section>
                  <h2 className="text-lg font-bold text-slate-900 mb-1">Reglas de PII</h2>
                  <p className="text-sm text-slate-500 mb-4">Configura que tipos de datos personales se detectan y anonimizan automaticamente.</p>
                  <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                    {piiRules.map((rule) => (
                      <div key={rule.id} className="flex items-center justify-between px-5 py-3 border-b border-slate-100 last:border-0 hover:bg-slate-50/50 transition-colors">
                        <div className="flex items-center gap-3">
                          <span className="px-2 py-0.5 text-[10px] font-bold bg-slate-100 text-slate-500 rounded uppercase">{rule.category}</span>
                          <span className="text-sm text-slate-800">{rule.label}</span>
                        </div>
                        <button
                          onClick={() => setPiiStates((s) => ({ ...s, [rule.id]: !s[rule.id] }))}
                          className={`relative w-10 h-5 rounded-full transition-colors ${piiStates[rule.id] ? "bg-primary" : "bg-slate-300"}`}
                        >
                          <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${piiStates[rule.id] ? "left-[22px]" : "left-0.5"}`} />
                        </button>
                      </div>
                    ))}
                  </div>
                </section>

                {/* Substitution Technique */}
                <section>
                  <h2 className="text-lg font-bold text-slate-900 mb-1">Tecnica de Sustitucion</h2>
                  <p className="text-sm text-slate-500 mb-4">Elige como se reemplazan los datos personales detectados.</p>
                  <div className="space-y-3">
                    {[
                      { id: "redacted", title: "Redaccion total (REDACTED)", desc: "Reemplaza todos los datos con [REDACTED]. Mascarado estatico sin contexto." },
                      { id: "synthetic", title: "Sustitucion sintetica ([PERSONA_1])", desc: "Mantiene coherencia del texto con datos ficticios realistas. Recomendado para soporte." },
                      { id: "aes256", title: "Cifrado reversible (AES-256)", desc: "Cifrado reversible con clave maestra. Permite recuperacion autorizada de datos originales." },
                    ].map((opt) => (
                      <label key={opt.id}
                        className={`flex items-start gap-4 p-4 rounded-xl border cursor-pointer transition-all ${
                          substitutionTechnique === opt.id
                            ? "border-primary bg-primary/5 shadow-sm"
                            : "border-slate-200 bg-white hover:border-slate-300"
                        }`}>
                        <div className={`mt-0.5 w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 transition-colors ${
                          substitutionTechnique === opt.id ? "border-primary bg-primary" : "border-slate-300"
                        }`}>
                          {substitutionTechnique === opt.id && <IconCheck />}
                        </div>
                        <div>
                          <input type="radio" name="technique" value={opt.id} checked={substitutionTechnique === opt.id}
                            onChange={(e) => setSubstitutionTechnique(e.target.value)} className="sr-only" />
                          <p className="text-sm font-semibold text-slate-900">{opt.title}</p>
                          <p className="text-xs text-slate-500 mt-0.5">{opt.desc}</p>
                        </div>
                      </label>
                    ))}
                  </div>
                </section>

                {/* AI Sensitivity */}
                <section>
                  <h2 className="text-lg font-bold text-slate-900 mb-1">Nivel de Sensibilidad IA</h2>
                  <p className="text-sm text-slate-500 mb-4">Ajusta el umbral de deteccion de PII por el modelo de IA.</p>
                  <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-bold text-slate-400 uppercase">Conservador</span>
                      <span className={`text-sm font-bold ${sensitivityColor}`}>{sensitivityLabel} ({sensitivity}%)</span>
                      <span className="text-xs font-bold text-slate-400 uppercase">Agresivo</span>
                    </div>
                    <input type="range" min="0" max="100" value={sensitivity} onChange={(e) => setSensitivity(Number(e.target.value))}
                      className="w-full h-2 bg-slate-200 rounded-full appearance-none cursor-pointer accent-primary [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:shadow-md" />
                    <p className="text-xs text-slate-500 mt-3 leading-relaxed">
                      Configuracion actual ({sensitivity}%) utiliza modelos transformadores avanzados para detectar PII en lenguaje natural
                      con un umbral de confianza moderado, minimizando falsos positivos en contextos tecnicos.
                    </p>
                  </div>
                </section>
              </div>
            )}

            {activeTab === "integrations" && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-bold text-slate-900 mb-1">Sistemas Conectados</h2>
                  <p className="text-sm text-slate-500">Gestiona las integraciones con sistemas de ticketing externos.</p>
                </div>
                <div className="space-y-3">
                  {integrations.map((sys) => (
                    <div key={sys.system_name} className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                      <div className="p-5 flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-white text-sm font-bold ${systemBgColor(sys.system_name)}`}>
                            {sys.display_name.slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <p className="text-sm font-bold text-slate-900">{sys.display_name}</p>
                              <span className={`w-2 h-2 rounded-full ${statusDot(sys.last_connection_status)}`} />
                              {sys.is_mock && <span className="px-1.5 py-0.5 text-[9px] font-bold bg-amber-100 text-amber-700 rounded">MOCK</span>}
                              {!sys.is_active && <span className="px-1.5 py-0.5 text-[9px] font-bold bg-slate-100 text-slate-500 rounded">INACTIVO</span>}
                            </div>
                            <p className="text-xs text-slate-500">
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
                            className="px-3 py-1.5 text-xs font-semibold text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
                          >
                            {expandedSystem === sys.system_name ? "Cerrar" : "Gestionar"}
                          </button>
                        </div>
                      </div>

                      {/* Test result */}
                      {testResult[sys.system_name] && (
                        <div className={`mx-5 mb-3 px-3 py-2 rounded-lg text-xs font-medium ${
                          testResult[sys.system_name].status === "connected"
                            ? "bg-green-50 text-green-700 border border-green-200"
                            : "bg-red-50 text-red-700 border border-red-200"
                        }`}>
                          {testResult[sys.system_name].message}
                        </div>
                      )}

                      {/* Expanded edit panel */}
                      {expandedSystem === sys.system_name && (
                        <div className="border-t border-slate-200 p-5 bg-slate-50/50 space-y-4">
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <label className="block text-xs font-semibold text-slate-700 mb-1">URL Base</label>
                              <input
                                type="text"
                                value={String(editForm.base_url || "")}
                                onChange={(e) => setEditForm((f) => ({ ...f, base_url: e.target.value }))}
                                placeholder="https://..."
                                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                              />
                            </div>
                            <div>
                              <label className="block text-xs font-semibold text-slate-700 mb-1">Token (dejar vacio para mantener actual)</label>
                              <input
                                type="password"
                                value={String(editForm.auth_token || "")}
                                onChange={(e) => setEditForm((f) => ({ ...f, auth_token: e.target.value }))}
                                placeholder={sys.auth_token_masked}
                                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                              />
                            </div>
                            <div>
                              <label className="block text-xs font-semibold text-slate-700 mb-1">Email</label>
                              <input
                                type="email"
                                value={String(editForm.auth_email || "")}
                                onChange={(e) => setEditForm((f) => ({ ...f, auth_email: e.target.value }))}
                                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                              />
                            </div>
                            <div>
                              <label className="block text-xs font-semibold text-slate-700 mb-1">Proyecto</label>
                              <input
                                type="text"
                                value={String(editForm.project_key || "")}
                                onChange={(e) => setEditForm((f) => ({ ...f, project_key: e.target.value }))}
                                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                              />
                            </div>
                          </div>

                          {sys.connector_type === "jira" && (
                            <div className="grid grid-cols-3 gap-4">
                              <div>
                                <label className="block text-xs font-semibold text-slate-700 mb-1">Board ID</label>
                                <input
                                  type="text"
                                  value={String(editForm.board_id || "")}
                                  onChange={(e) => setEditForm((f) => ({ ...f, board_id: e.target.value }))}
                                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                                />
                              </div>
                              <div>
                                <label className="block text-xs font-semibold text-slate-700 mb-1">Issue Type ID</label>
                                <input
                                  type="text"
                                  value={String(editForm.issue_type_id || "")}
                                  onChange={(e) => setEditForm((f) => ({ ...f, issue_type_id: e.target.value }))}
                                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                                />
                              </div>
                              <div>
                                <label className="block text-xs font-semibold text-slate-700 mb-1">Parent Key</label>
                                <input
                                  type="text"
                                  value={String(editForm.parent_key || "")}
                                  onChange={(e) => setEditForm((f) => ({ ...f, parent_key: e.target.value }))}
                                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                                />
                              </div>
                            </div>
                          )}

                          <div className="grid grid-cols-3 gap-4">
                            <div>
                              <label className="block text-xs font-semibold text-slate-700 mb-1">Polling (seg)</label>
                              <input
                                type="number"
                                min={5}
                                value={Number(editForm.polling_interval_sec || 60)}
                                onChange={(e) => setEditForm((f) => ({ ...f, polling_interval_sec: Number(e.target.value) }))}
                                className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                              />
                            </div>
                            <div className="flex items-end gap-4">
                              <label className="flex items-center gap-2 cursor-pointer">
                                <button
                                  onClick={() => setEditForm((f) => ({ ...f, is_active: !f.is_active }))}
                                  className={`relative w-10 h-5 rounded-full transition-colors ${editForm.is_active ? "bg-primary" : "bg-slate-300"}`}
                                >
                                  <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${editForm.is_active ? "left-[22px]" : "left-0.5"}`} />
                                </button>
                                <span className="text-xs font-semibold text-slate-700">Activo</span>
                              </label>
                              <label className="flex items-center gap-2 cursor-pointer">
                                <button
                                  onClick={() => setEditForm((f) => ({ ...f, is_mock: !f.is_mock }))}
                                  className={`relative w-10 h-5 rounded-full transition-colors ${editForm.is_mock ? "bg-amber-400" : "bg-slate-300"}`}
                                >
                                  <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${editForm.is_mock ? "left-[22px]" : "left-0.5"}`} />
                                </button>
                                <span className="text-xs font-semibold text-slate-700">Mock</span>
                              </label>
                            </div>
                          </div>

                          <div className="flex justify-end gap-2 pt-2">
                            <button
                              onClick={() => setExpandedSystem(null)}
                              className="px-4 py-2 text-sm font-semibold text-slate-600 border border-slate-200 rounded-lg hover:bg-white transition-colors"
                            >
                              Cancelar
                            </button>
                            <button
                              onClick={() => handleSave(sys.system_name)}
                              disabled={saving}
                              className="px-5 py-2 bg-primary text-white text-sm font-bold rounded-lg hover:bg-blue-600 transition-colors shadow-lg shadow-primary/20 disabled:opacity-50"
                            >
                              {saving ? "Guardando..." : "Guardar"}
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                  {integrations.length === 0 && (
                    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-10 text-center">
                      <p className="text-sm text-slate-500">Cargando integraciones...</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === "general" && (
              <div className="space-y-6">
                <h2 className="text-lg font-bold text-slate-900 mb-1">Configuracion General</h2>
                <p className="text-sm text-slate-500">Parametros generales de la plataforma.</p>
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">Proveedor LLM</label>
                    <select className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent">
                      <option>Azure OpenAI (Produccion GDPR)</option>
                      <option>Ollama (Desarrollo local)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">Modelo</label>
                    <select className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent">
                      <option>gpt-4o-mini</option>
                      <option>gpt-4o</option>
                      <option>llama3.1:8b</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">Intervalo de refresco del board (seg)</label>
                    <input
                      type="number"
                      min={5}
                      value={generalLoaded ? pollingInterval : 60}
                      onChange={(e) => setPollingInterval(Number(e.target.value))}
                      className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                    />
                  </div>
                </div>
                <div className="flex justify-end">
                  <button
                    onClick={handleSaveGeneral}
                    className="px-5 py-2 bg-primary text-white text-sm font-bold rounded-lg hover:bg-blue-600 transition-colors shadow-lg shadow-primary/20"
                  >
                    Guardar configuracion
                  </button>
                </div>
              </div>
            )}

            {activeTab === "tickets" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-slate-900 mb-1">Gestion de Tickets</h2>
                    <p className="text-sm text-slate-500">Administra los tickets ingestados. Puedes eliminar tickets y sus datos asociados.</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-500">{adminTickets.length} ticket{adminTickets.length !== 1 ? "s" : ""}</span>
                    <button onClick={fetchAdminTickets} className="p-2 text-slate-500 hover:bg-slate-100 rounded-lg transition-colors" title="Refrescar">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                      </svg>
                    </button>
                  </div>
                </div>
                {adminLoading ? (
                  <div className="text-center py-20">
                    <div className="w-10 h-10 mx-auto border-[3px] border-primary/20 border-t-primary rounded-full animate-spin mb-4" />
                    <p className="text-sm text-slate-500">Cargando tickets...</p>
                  </div>
                ) : adminTickets.length === 0 ? (
                  <div className="text-center py-16 bg-white rounded-xl border border-slate-200 shadow-sm">
                    <div className="w-14 h-14 mx-auto mb-4 bg-primary/5 rounded-2xl flex items-center justify-center border border-primary/10">
                      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-primary">
                        <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
                      </svg>
                    </div>
                    <p className="text-sm font-semibold text-slate-900 mb-1">No hay tickets ingestados</p>
                    <p className="text-xs text-slate-500">Los tickets apareceran aqui una vez ingestados desde la vista de Incidencias</p>
                  </div>
                ) : (
                  <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-slate-200 bg-slate-50">
                          <th className="text-left px-4 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-wider">KOSIN Key</th>
                          <th className="text-left px-4 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-wider">Origen</th>
                          <th className="text-left px-4 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-wider">Source Key</th>
                          <th className="text-left px-4 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-wider">Resumen</th>
                          <th className="text-left px-4 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-wider">Prioridad</th>
                          <th className="text-left px-4 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-wider">Estado</th>
                          <th className="text-left px-4 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-wider">Creado</th>
                          <th className="text-right px-4 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-wider">Accion</th>
                        </tr>
                      </thead>
                      <tbody>
                        {adminTickets.map((t) => {
                          const pr = priorityConfig[t.priority] || { bg: "bg-slate-100", text: "text-slate-600", label: t.priority };
                          const st = statusConfig[t.status] || { bg: "bg-slate-100", text: "text-slate-600", label: t.status };
                          return (
                            <tr key={t.id} className="border-b border-slate-100 hover:bg-slate-50/50 transition-colors">
                              <td className="px-4 py-3 text-sm font-semibold text-primary">{t.kosin_ticket_id}</td>
                              <td className="px-4 py-3">
                                <span className="px-2 py-0.5 text-[10px] font-bold bg-slate-100 text-slate-600 rounded uppercase">{t.source_system}</span>
                              </td>
                              <td className="px-4 py-3 text-sm text-slate-600">{t.source_ticket_id}</td>
                              <td className="px-4 py-3 text-sm text-slate-800 max-w-[300px] truncate">{t.summary}</td>
                              <td className="px-4 py-3">
                                <span className={`px-2 py-0.5 text-[10px] font-bold rounded-full ${pr.bg} ${pr.text}`}>{pr.label}</span>
                              </td>
                              <td className="px-4 py-3">
                                <span className={`px-2 py-0.5 text-[10px] font-bold rounded-full ${st.bg} ${st.text}`}>{st.label}</span>
                              </td>
                              <td className="px-4 py-3 text-xs text-slate-500">{new Date(t.created_at).toLocaleDateString("es-ES")}</td>
                              <td className="px-4 py-3 text-right">
                                <button onClick={() => setConfirmDelete(t.kosin_ticket_id)}
                                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors">
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
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 p-6 max-w-sm w-full mx-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center shrink-0">
                <IconTrash />
              </div>
              <div>
                <p className="text-sm font-bold text-slate-900">Eliminar ticket</p>
                <p className="text-xs text-slate-500">Esta accion no se puede deshacer</p>
              </div>
            </div>
            <p className="text-sm text-slate-700 mb-1">
              Se eliminara <span className="font-semibold text-primary">{confirmDelete}</span> de KOSIN y de la base de datos, incluyendo historial de chat y mapa de sustitucion.
            </p>
            {deleteError && (
              <div className="mt-3 px-3 py-2 bg-red-50 text-red-700 text-xs font-medium rounded-lg border border-red-200">
                {deleteError}
              </div>
            )}
            <div className="flex justify-end gap-2 mt-5">
              <button
                onClick={() => { setConfirmDelete(null); setDeleteError(null); }}
                className="px-4 py-2 text-sm font-semibold text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
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
