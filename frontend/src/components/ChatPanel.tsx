"use client";

import { useState, useRef, useEffect } from "react";
import { useAppStore } from "@/stores/appStore";
import { ChatMessage } from "./ChatMessage";
import { IngestProgress } from "./IngestProgress";
import { BoardTicket } from "@/types";

// Reusable SVG icons
const IconShield = ({ size = 24, className = "" }: { size?: number; className?: string }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
  </svg>
);
const IconChat = ({ size = 24, className = "" }: { size?: number; className?: string }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
  </svg>
);
const IconLock = ({ size = 24, className = "" }: { size?: number; className?: string }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
  </svg>
);
const IconAgent = ({ className = "" }: { className?: string }) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 110 2h-1.07A7.001 7.001 0 0113 22h-2a7.001 7.001 0 01-6.93-6H3a1 1 0 110-2h1a7 7 0 017-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 012-2z"/>
  </svg>
);
const IconSend = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>
);
const IconSync = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
  </svg>
);
const IconBolt = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
  </svg>
);
const IconPriority = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
  </svg>
);
const IconShieldCheck = ({ size = 24, className = "" }: { size?: number; className?: string }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 12 15 15 10"/>
  </svg>
);
const IconClip = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
  </svg>
);

const KOSIN_BASE = "https://umane.emeal.nttdata.com/jiraito/browse";

const IconExternalLink = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
  </svg>
);

interface Props {
  ticketId: number | null;
  boardTicket: BoardTicket | null;
  onSendMessage: (message: string, isChip?: boolean) => void;
  onFinishTicket: () => void;
  onSyncToClient: (comment: string) => void;
  onCloseTicket: () => void;
  onConfirmIngest: (key: string) => void;
}

export function ChatPanel({ ticketId, boardTicket, onSendMessage, onFinishTicket, onSyncToClient, onCloseTicket, onConfirmIngest }: Props) {
  const [input, setInput] = useState("");
  const [isSyncing, setIsSyncing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { chatMessages, isStreaming, isIngesting, tickets, suggestedChips, piiWarnings } = useAppStore();
  const messages = ticketId ? chatMessages[ticketId] || [] : [];
  const ticket = tickets.find((t) => t.id === ticketId);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, isStreaming]);

  const handleSend = (text?: string, isChip: boolean = false) => {
    const msg = (text || input).trim();
    if (!msg || isStreaming) return;
    setInput("");
    onSendMessage(msg, isChip);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  // Empty state
  if (!ticketId && !boardTicket) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-0 overflow-hidden bg-slate-50/50 dark:bg-slate-900">
        <div className="text-center max-w-md">
          <div className="w-20 h-20 mx-auto mb-6 bg-primary/5 rounded-2xl flex items-center justify-center border border-primary/10">
            <IconShield size={36} className="text-primary" />
          </div>
          <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-2">Plataforma de Anonimizacion</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-8">Selecciona una incidencia del panel izquierdo para comenzar a trabajar de forma segura</p>
          <div className="grid grid-cols-3 gap-3">
            {[
              { icon: <IconShield size={18} className="text-primary" />, title: "Anonimizacion", desc: "Datos protegidos" },
              { icon: <IconChat size={18} className="text-primary" />, title: "Asistente IA", desc: "Guia inteligente" },
              { icon: <IconLock size={18} className="text-primary" />, title: "Cifrado AES-256", desc: "Extremo a extremo" },
            ].map((f, i) => (
              <div key={i} className="p-4 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm text-center">
                <div className="w-10 h-10 mx-auto mb-2 bg-primary/10 rounded-lg flex items-center justify-center">{f.icon}</div>
                <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 mb-0.5">{f.title}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Pre-ingest
  if (boardTicket && !ticketId) {
    const pColors: Record<string, string> = { Critical: "#EF4444", High: "#F59E0B", Medium: "#3B82F6", Low: "#10B981" };
    const pLabels: Record<string, string> = { Critical: "Critica", High: "Alta", Medium: "Media", Low: "Baja" };
    const srcLabels: Record<string, string> = { kosin: "KOSIN", stdvert1: "STDVERT1", remedy: "Remedy", servicenow: "ServiceNow", jira: "Jira" };
    const srcColors: Record<string, string> = { stdvert1: "#6366F1", kosin: "#3B82F6", remedy: "#F59E0B", servicenow: "#10B981", jira: "#3B82F6" };
    const srcLabel = srcLabels[boardTicket.source_system] || boardTicket.source_system.toUpperCase();
    const srcColor = srcColors[boardTicket.source_system] || "#6B7280";

    return (
      <div className="flex flex-col h-full min-h-0">
        <div className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-6 py-4 shrink-0">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-xs font-bold text-white" style={{ backgroundColor: srcColor }}>{srcLabel}</span>
            <span className="text-sm font-bold text-slate-900 dark:text-slate-100">{boardTicket.key}</span>
            <span className="text-slate-300 dark:text-slate-600">/</span>
            <span className="text-xs text-slate-500 dark:text-slate-400">{boardTicket.issue_type}</span>
            <span className="text-slate-300 dark:text-slate-600">/</span>
            <span className="flex items-center gap-1 text-xs font-bold" style={{ color: pColors[boardTicket.priority] || "#3B82F6" }}>
              <IconPriority />
              {pLabels[boardTicket.priority] || boardTicket.priority}
            </span>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center px-6 bg-slate-50/50 dark:bg-slate-900">
          <div className="max-w-lg text-center">
            {isIngesting ? (
              <div role="status" className="w-full flex justify-center">
                <IngestProgress />
              </div>
            ) : (
              <div>
                <div className="w-16 h-16 mx-auto mb-5 bg-primary/10 rounded-2xl flex items-center justify-center border border-primary/20">
                  <IconShieldCheck size={32} className="text-primary" />
                </div>
                <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-3">Incidencia pendiente de atender</h2>
                <div className="bg-white dark:bg-slate-800 rounded-xl p-5 mb-5 text-left border border-slate-200 dark:border-slate-700 shadow-sm">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-sm font-bold text-slate-900 dark:text-slate-100">{boardTicket.key}</span>
                    <span className="px-2 py-0.5 rounded text-xs font-bold text-white" style={{ backgroundColor: srcColor }}>{srcLabel}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div><span className="text-slate-400 dark:text-slate-500">Tipo</span><p className="font-medium text-slate-800 dark:text-slate-200">{boardTicket.issue_type}</p></div>
                    <div><span className="text-slate-400 dark:text-slate-500">Prioridad</span>
                      <p className="font-semibold flex items-center gap-1" style={{ color: pColors[boardTicket.priority] || "#3B82F6" }}>
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: pColors[boardTicket.priority] }} />
                        {pLabels[boardTicket.priority] || boardTicket.priority}
                      </p>
                    </div>
                    <div><span className="text-slate-400 dark:text-slate-500">Estado</span><p className="font-medium text-slate-800 dark:text-slate-200">{boardTicket.status}</p></div>
                    <div><span className="text-slate-400 dark:text-slate-500">Origen</span><p className="font-medium text-slate-800 dark:text-slate-200">{srcLabel}</p></div>
                  </div>
                </div>
                <div className="flex flex-col sm:flex-row gap-3 justify-center">
                  <button onClick={() => onConfirmIngest(boardTicket.key)}
                    className="px-8 py-3 bg-primary text-white rounded-xl text-sm font-bold hover:bg-blue-600 active:scale-[0.98] transition-all shadow-lg shadow-primary/20 inline-flex items-center gap-2">
                    <IconShield size={18} className="text-white" />
                    Atender esta incidencia
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  const statusLabels: Record<string, string> = { open: "Pendiente", in_progress: "En Progreso", resolved: "Resuelto", closed: "Cerrado" };
  const pLabels: Record<string, string> = { critical: "Critica", high: "Alta", medium: "Media", low: "Baja" };
  const pColors: Record<string, string> = { critical: "#EF4444", high: "#F59E0B", medium: "#3B82F6", low: "#10B981" };
  const isThinking = isStreaming;

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Chat Header */}
      {ticket && (
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between bg-white dark:bg-slate-800">
          <div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">[ANON] {ticket.kosin_id}</h2>
            <div className="flex items-center gap-3 mt-1">
              <a
                href={`${KOSIN_BASE}/${ticket.kosin_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:text-blue-600 transition-colors"
              >
                Ver Incidencia Anonimizada
                <IconExternalLink />
              </a>
              {ticket.source_ticket_id && (
                <a
                  href={`${KOSIN_BASE}/${ticket.source_ticket_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 transition-colors"
                >
                  Ver Ticket Origen
                  <IconExternalLink />
                </a>
              )}
            </div>
          </div>
          <div className="flex flex-col items-end gap-1.5">
            <span className="px-3 py-1 bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 text-xs font-bold rounded-lg uppercase">
              {statusLabels[ticket.status] || ticket.status}
            </span>
            <span className="flex items-center gap-1.5 px-3 py-1 text-xs font-bold rounded-lg uppercase" style={{ backgroundColor: `${pColors[ticket.priority] || "#3B82F6"}15`, color: pColors[ticket.priority] || "#3B82F6" }}>
              <IconPriority />
              {pLabels[ticket.priority] || ticket.priority}
            </span>
          </div>
        </div>
      )}

      {/* PII warning banner */}
      {ticketId && piiWarnings[ticketId] && (
        <div className="px-6 py-2.5 bg-amber-50 dark:bg-amber-900/20 border-b border-amber-200 dark:border-amber-800/50 flex items-center gap-2.5 shrink-0">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-amber-500 shrink-0">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <span className="text-xs font-medium text-amber-700 dark:text-amber-300">{piiWarnings[ticketId]}</span>
        </div>
      )}

      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto p-6 custom-scrollbar bg-slate-50/50 dark:bg-slate-900" role="log" aria-label="Historial de chat" aria-live="polite">
        {messages.length === 0 && !isThinking && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <IconChat size={48} className="text-slate-300 dark:text-slate-600 mx-auto mb-3" />
              <p className="text-sm text-slate-400 dark:text-slate-500">Escribe un mensaje para comenzar</p>
            </div>
          </div>
        )}

        {messages.map((msg, idx) => <ChatMessage key={idx} message={msg} />)}

        {isThinking && (
          <div className="flex gap-4 max-w-[85%] mb-6" role="status">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 border border-primary/20">
              <IconAgent className="text-primary" />
            </div>
            <div className="bg-white dark:bg-slate-800 border-l-4 border-primary shadow-sm rounded-r-xl rounded-bl-xl p-4">
              <div className="flex items-center gap-3">
                <svg className="animate-spin w-4 h-4 text-primary shrink-0" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <span className="text-sm text-slate-500 dark:text-slate-400">Pensando...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested action chips */}
      {suggestedChips.length > 0 && !isStreaming && (
        <div className="px-6 py-3 bg-slate-50/50 dark:bg-slate-900 border-t border-slate-100 dark:border-slate-800" role="group" aria-label="Acciones sugeridas">
          <div className="flex flex-wrap gap-2">
            {suggestedChips.map((chip, i) => (
              <button key={i} onClick={() => handleSend(chip, true)}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 rounded-full text-xs font-medium hover:border-primary hover:text-primary transition-all shadow-sm cursor-pointer">
                <IconBolt />
                {chip}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="p-6 border-t border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
        <div className="relative mb-4">
          <label htmlFor="chat-input" className="sr-only">Mensaje al agente IA</label>
          <textarea id="chat-input" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown}
            placeholder="Escribe tu mensaje..." disabled={isStreaming} rows={2}
            className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 pr-14 text-sm text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-primary focus:border-transparent transition-all outline-none resize-none disabled:opacity-50 placeholder:text-slate-400 dark:placeholder:text-slate-500" />
          <button onClick={() => handleSend()} disabled={isStreaming || !input.trim()} aria-label="Enviar mensaje"
            className="absolute right-3 bottom-3 w-8 h-8 bg-primary text-white rounded-lg flex items-center justify-center hover:bg-blue-600 transition-colors shadow-lg shadow-primary/20 disabled:bg-slate-300 dark:disabled:bg-slate-600 disabled:shadow-none disabled:cursor-not-allowed">
            <IconSend />
          </button>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex gap-2">
            <button className="p-2 text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors" title="Adjuntar archivo">
              <IconClip />
            </button>
          </div>
          <div className="flex gap-3" role="group" aria-label="Acciones del ticket">
            {ticket && ticket.status !== "resolved" && ticket.status !== "closed" && (
              <>
                <button
                  onClick={() => {
                    const agentMsgs = messages.filter((m) => m.role === "agent");
                    const lastAgent = agentMsgs[agentMsgs.length - 1];
                    if (!lastAgent) return;
                    const comment = lastAgent.content.replace(/\[CHIPS[:\s].*?\]/gs, "").trim();
                    if (!comment) return;
                    setIsSyncing(true);
                    onSyncToClient(comment);
                    setTimeout(() => setIsSyncing(false), 2000);
                  }}
                  disabled={isSyncing}
                  className="flex items-center gap-2 px-4 py-2 bg-teal-500 text-white rounded-lg text-sm font-bold hover:bg-teal-600 transition-colors shadow-lg shadow-teal-500/20 disabled:opacity-50">
                  <IconSync />
                  {isSyncing ? "Sincronizando..." : "Sincronizar con origen"}
                </button>
<button onClick={onFinishTicket}
                  className="flex items-center gap-2 px-4 py-2 border-2 border-primary text-primary rounded-lg text-sm font-bold hover:bg-primary hover:text-white transition-all">
                  Finalizar ticket
                </button>
              </>
            )}
            {ticket && ticket.status === "resolved" && (
              <button onClick={onCloseTicket}
                className="flex items-center gap-2 px-4 py-2 bg-red-500 text-white rounded-lg text-sm font-bold hover:bg-red-600 transition-colors shadow-lg shadow-red-500/20">
                <IconLock size={16} className="text-white" />
                Cerrar ticket
              </button>
            )}
          </div>
        </div>
      </div>

    </div>
  );
}
