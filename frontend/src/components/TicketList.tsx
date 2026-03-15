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

const sourceSystemConfig: Record<string, string> = {
  kosin: "K", remedy: "R", servicenow: "SN",
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
      <div className="flex border-b border-slate-700/50 shrink-0">
        <button
          onClick={() => setActiveTab("pendientes")}
          className={`flex-1 px-4 py-3 text-xs font-bold uppercase tracking-wider transition-colors relative ${
            activeTab === "pendientes"
              ? "text-primary"
              : "text-slate-500 hover:text-slate-300"
          }`}
        >
          <span className="flex items-center justify-center gap-2">
            Pendientes
            <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
              activeTab === "pendientes"
                ? "bg-primary/20 text-primary"
                : "bg-slate-700 text-slate-400"
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
              : "text-slate-500 hover:text-slate-300"
          }`}
        >
          <span className="flex items-center justify-center gap-2">
            En Atencion
            <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
              activeTab === "en_atencion"
                ? "bg-primary/20 text-primary"
                : "bg-slate-700 text-slate-400"
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
              const srcLabel = sourceSystemConfig[bt.source_system] || bt.source_system.slice(0, 2).toUpperCase();

              return (
                <div key={bt.key} role="listitem"
                  onClick={() => onSelectBoardTicket(bt.key)}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelectBoardTicket(bt.key); } }}
                  tabIndex={0} aria-selected={isSelected}
                  className={`p-3 rounded-lg cursor-pointer transition-all ${
                    isSelected ? "bg-primary/10 border border-primary/30" : "bg-slate-800/40 border border-slate-700/50 hover:bg-slate-800/60"
                  }`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-xs font-bold text-primary">{bt.key}</span>
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: priority.color, boxShadow: `0 0 8px ${priority.shadow}` }} />
                  </div>
                  <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed mb-3">
                    {bt.issue_type} — {bt.status}
                  </p>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-slate-500">{bt.status}</span>
                    <div className="w-4 h-4 rounded-sm bg-slate-700 flex items-center justify-center text-[8px] font-bold text-slate-400">{srcLabel}</div>
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
