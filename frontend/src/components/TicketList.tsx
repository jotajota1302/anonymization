"use client";

import { useState } from "react";
import { TicketSummary, BoardTicket } from "@/types";
import { TicketCard } from "./TicketCard";

const priorityConfig: Record<string, { color: string; shadow: string; label: string }> = {
  Critical: { color: "#EF4444", shadow: "rgba(239,68,68,0.5)", label: "Critica" },
  High:     { color: "#F59E0B", shadow: "rgba(245,158,11,0.5)", label: "Alta" },
  Medium:   { color: "#3B82F6", shadow: "rgba(59,130,246,0.5)", label: "Media" },
  Low:      { color: "#10B981", shadow: "rgba(16,185,129,0.5)", label: "Baja" },
};

const sourceSystemLabels: Record<string, string> = {
  kosin: "KOSIN", remedy: "Remedy", servicenow: "ServiceNow", jira: "Jira",
};

interface Props {
  boardTickets: BoardTicket[];
  tickets: TicketSummary[];
  selectedTicketId: number | null;
  selectedBoardKey: string | null;
  onSelectTicket: (id: number) => void;
  onSelectBoardTicket: (key: string) => void;
}

type ListTab = "pendientes" | "en_atencion";

export function TicketList({ boardTickets, tickets, selectedTicketId, selectedBoardKey, onSelectTicket, onSelectBoardTicket }: Props) {
  const [activeTab, setActiveTab] = useState<ListTab>("pendientes");

  const pendingBoard = boardTickets.filter((bt) => !bt.already_ingested);
  const activeTickets = tickets.filter((t) => t.status !== "closed");

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
        {activeTab === "pendientes" && (
          <div className="space-y-3" role="list" aria-label="Incidencias pendientes">
            {pendingBoard.map((bt) => {
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
            {pendingBoard.length === 0 && <p className="text-xs text-slate-500 text-center py-8">Sin incidencias pendientes</p>}
          </div>
        )}

        {activeTab === "en_atencion" && (
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
