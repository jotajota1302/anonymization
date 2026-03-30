"use client";

import { useState } from "react";
import { TicketSummary, BoardTicket } from "@/types";
import { TicketCard } from "./TicketCard";
import { useAppStore, BoardFilters } from "@/stores/appStore";

const priorityConfig: Record<string, { color: string; shadow: string; label: string }> = {
  Critical: { color: "#EF4444", shadow: "rgba(239,68,68,0.5)", label: "Critica" },
  High:     { color: "#F59E0B", shadow: "rgba(245,158,11,0.5)", label: "Alta" },
  Medium:   { color: "#3B82F6", shadow: "rgba(59,130,246,0.5)", label: "Media" },
  Low:      { color: "#10B981", shadow: "rgba(16,185,129,0.5)", label: "Baja" },
};

const sourceSystemLabels: Record<string, string> = {
  kosin: "KOSIN", stdvert1: "STDVERT1", remedy: "Remedy", servicenow: "ServiceNow", jira: "Jira",
};

interface Props {
  boardTickets: BoardTicket[];
  tickets: TicketSummary[];
  selectedTicketId: number | null;
  selectedBoardKey: string | null;
  onSelectTicket: (id: number) => void;
  onSelectBoardTicket: (key: string) => void;
  onApplyFilters?: () => void;
  isLoadingBoard?: boolean;
  isLoadingTickets?: boolean;
}

type ListTab = "pendientes" | "en_atencion";

export function TicketList({ boardTickets, tickets, selectedTicketId, selectedBoardKey, onSelectTicket, onSelectBoardTicket, onApplyFilters, isLoadingBoard, isLoadingTickets }: Props) {
  const [activeTab, setActiveTab] = useState<ListTab>("pendientes");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [showFilters, setShowFilters] = useState(false);
  const { boardFilters, setBoardFilters, resetBoardFilters } = useAppStore();

  const pendingBoard = boardTickets.filter((bt) => !bt.already_ingested);
  const activeTickets = tickets.filter((t) => t.status !== "closed");

  const filteredPending = searchQuery.trim()
    ? pendingBoard.filter((bt) => {
        const q = searchQuery.toLowerCase();
        return (
          bt.key.toLowerCase().includes(q) ||
          bt.issue_type.toLowerCase().includes(q) ||
          bt.status.toLowerCase().includes(q) ||
          bt.priority.toLowerCase().includes(q) ||
          bt.source_system.toLowerCase().includes(q)
        );
      })
    : pendingBoard;

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Tabs */}
      <div className="flex border-b border-slate-200 dark:border-slate-700/50 shrink-0">
        <button
          onClick={() => setActiveTab("pendientes")}
          className={`flex-1 px-4 py-3 text-xs font-bold uppercase tracking-wider transition-colors relative ${
            activeTab === "pendientes"
              ? "text-primary"
              : "text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300"
          }`}
        >
          <span className="flex items-center justify-center gap-2">
            Pendientes
            <span className={`px-1.5 py-0.5 rounded-full text-xs font-bold ${
              activeTab === "pendientes"
                ? "bg-primary/20 text-primary"
                : "bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-400"
            }`}>
              {pendingBoard.length}
            </span>
          </span>
          {activeTab === "pendientes" && (
            <span className="absolute bottom-0 left-2 right-2 h-0.5 bg-primary rounded-full" />
          )}
        </button>
        <button
          onClick={() => setActiveTab("en_atencion")}
          className={`flex-1 px-4 py-3 text-xs font-bold uppercase tracking-wider transition-colors relative ${
            activeTab === "en_atencion"
              ? "text-primary"
              : "text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300"
          }`}
        >
          <span className="flex items-center justify-center gap-2">
            En Atencion
            <span className={`px-1.5 py-0.5 rounded-full text-xs font-bold ${
              activeTab === "en_atencion"
                ? "bg-primary/20 text-primary"
                : "bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-400"
            }`}>
              {activeTickets.length}
            </span>
          </span>
          {activeTab === "en_atencion" && (
            <span className="absolute bottom-0 left-2 right-2 h-0.5 bg-primary rounded-full" />
          )}
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 custom-scrollbar min-h-0">
        {activeTab === "pendientes" && isLoadingBoard && (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <svg className="animate-spin h-8 w-8 text-primary/60" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <p className="text-xs text-slate-400 dark:text-slate-500">Cargando incidencias...</p>
          </div>
        )}

        {activeTab === "pendientes" && !isLoadingBoard && (
          <div className="space-y-3">
            {/* Buscador */}
            <div className="relative">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
              <input
                type="text"
                name="ticket-search"
                aria-label="Buscar por clave, tipo, estado"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Buscar por clave, tipo, estado..."
                className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/60 text-slate-700 dark:text-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50"
              />
              {searchQuery && (
                <button onClick={() => setSearchQuery("")} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
                </button>
              )}
            </div>
            {searchQuery && (
              <p className="text-xs text-slate-400 dark:text-slate-500">
                {filteredPending.length} de {pendingBoard.length} incidencias
              </p>
            )}
            {/* Filtros de origen */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowFilters(!showFilters)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/60 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700/60 transition-colors"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
                Filtros
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={`transition-transform ${showFilters ? "rotate-180" : ""}`}><path d="m6 9 6 6 6-6"/></svg>
              </button>
              {/* Presets rapidos */}
              <button onClick={() => { const d = new Date(); d.setDate(d.getDate() - 7); setBoardFilters({ date_from: d.toISOString().split("T")[0], date_to: null }); onApplyFilters?.(); }}
                className="px-2 py-1 text-xs rounded-md bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors">
                Ult. semana
              </button>
              <button onClick={() => { const d = new Date(); d.setMonth(d.getMonth() - 1); setBoardFilters({ date_from: d.toISOString().split("T")[0], date_to: null }); onApplyFilters?.(); }}
                className="px-2 py-1 text-xs rounded-md bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors">
                Ult. mes
              </button>
              <button onClick={() => { resetBoardFilters(); onApplyFilters?.(); }}
                className="px-2 py-1 text-xs rounded-md bg-slate-100 dark:bg-slate-700/50 text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors">
                Todas
              </button>
            </div>
            {showFilters && (
              <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/40 space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1 block">Desde</label>
                    <input type="date" value={boardFilters.date_from || ""} onChange={(e) => setBoardFilters({ date_from: e.target.value || null })}
                      className="w-full px-2 py-1.5 text-xs rounded border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1 block">Hasta</label>
                    <input type="date" value={boardFilters.date_to || ""} onChange={(e) => setBoardFilters({ date_to: e.target.value || null })}
                      className="w-full px-2 py-1.5 text-xs rounded border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200" />
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1 block">Prioridad</label>
                  <div className="flex flex-wrap gap-1.5">
                    {["Critical", "High", "Medium", "Low"].map((p) => {
                      const active = boardFilters.priority?.includes(p);
                      return (
                        <button key={p} onClick={() => {
                          const current = boardFilters.priority || [];
                          setBoardFilters({ priority: active ? current.filter((x) => x !== p) : [...current, p] });
                        }}
                          className={`px-2 py-1 text-xs rounded-md border transition-colors ${active ? "bg-primary/10 border-primary/30 text-primary font-bold" : "border-slate-200 dark:border-slate-600 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"}`}>
                          {priorityConfig[p]?.label || p}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1 block">Max. resultados</label>
                  <input type="number" min={1} max={200} value={boardFilters.max_results} onChange={(e) => setBoardFilters({ max_results: Number(e.target.value) || 50 })}
                    className="w-20 px-2 py-1.5 text-xs rounded border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200" />
                </div>
                <button onClick={() => { onApplyFilters?.(); setShowFilters(false); }}
                  className="w-full py-1.5 text-xs font-bold rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors">
                  Aplicar filtros
                </button>
              </div>
            )}
            <div role="list" aria-label="Incidencias pendientes" className="space-y-3">
            {filteredPending.map((bt) => {
              const priority = priorityConfig[bt.priority] || priorityConfig.Medium;
              const isSelected = bt.key === selectedBoardKey;
              const srcLabel = sourceSystemLabels[bt.source_system] || bt.source_system;
              const pLabel = { Critical: "Critica", High: "Alta", Medium: "Media", Low: "Baja" }[bt.priority] || bt.priority;

              return (
                <div key={bt.key} role="listitem"
                  onClick={() => onSelectBoardTicket(bt.key)}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelectBoardTicket(bt.key); } }}
                  tabIndex={0} aria-selected={isSelected}
                  className={`p-3.5 rounded-xl cursor-pointer transition-all ${
                    isSelected
                      ? "bg-primary/10 border border-primary/30 shadow-md shadow-primary/10"
                      : "bg-white dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-800/60 shadow hover:shadow-md"
                  }`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-sm font-bold text-primary">{bt.key}</span>
                    <span className="px-2 py-0.5 rounded text-xs font-bold uppercase" style={{ backgroundColor: `${priority.color}15`, color: priority.color }}>
                      {pLabel}
                    </span>
                  </div>
                  <p className="text-xs font-medium text-slate-700 dark:text-slate-200 mb-3">
                    {bt.issue_type}
                  </p>
                  <div className="flex items-center gap-4 text-xs text-slate-400 dark:text-slate-500">
                    <span className="flex items-center gap-1.5">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg>
                      <span className="font-medium text-slate-600 dark:text-slate-300">{srcLabel}</span>
                    </span>
                    <span className="text-slate-300 dark:text-slate-600">|</span>
                    <span className="flex items-center gap-1.5">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                      <span className="font-medium text-slate-600 dark:text-slate-300">{bt.status}</span>
                    </span>
                  </div>
                </div>
              );
            })}
            {filteredPending.length === 0 && (
              <p className="text-xs text-slate-500 text-center py-8">
                {searchQuery ? "Sin resultados para la busqueda" : "Sin incidencias pendientes"}
              </p>
            )}
            </div>
          </div>
        )}

        {activeTab === "en_atencion" && isLoadingTickets && (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <svg className="animate-spin h-8 w-8 text-primary/60" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <p className="text-xs text-slate-400 dark:text-slate-500">Cargando tickets...</p>
          </div>
        )}

        {activeTab === "en_atencion" && !isLoadingTickets && (
          <div className="space-y-3" role="list" aria-label="Incidencias en atencion">
            {activeTickets.map((ticket) => (
              <TicketCard key={ticket.id} ticket={ticket} isSelected={ticket.id === selectedTicketId} onClick={() => onSelectTicket(ticket.id)} />
            ))}
            {activeTickets.length === 0 && <p className="text-xs text-slate-500 text-center py-8">Sin incidencias activas</p>}
          </div>
        )}
      </div>
    </div>
  );
}
