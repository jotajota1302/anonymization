"use client";

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

export function TicketList({ boardTickets, tickets, selectedTicketId, selectedBoardKey, onSelectTicket, onSelectBoardTicket }: Props) {
  const pendingBoard = boardTickets.filter((bt) => !bt.already_ingested);
  const activeTickets = tickets.filter((t) => t.status !== "closed");

  return (
    <div className="flex flex-col h-full">
      {/* PENDIENTES */}
      <div className="p-4 border-b border-slate-800/50">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">
              Pendientes ({pendingBoard.length})
            </h3>
          </div>
        </div>
        <div className="space-y-3">
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
          {pendingBoard.length === 0 && <p className="text-xs text-slate-500 text-center py-4">Sin incidencias pendientes</p>}
        </div>
      </div>

      {/* EN ATENCION */}
      <div className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">
              En Atencion ({activeTickets.length})
            </h3>
          </div>
        </div>
        <div className="space-y-3">
          {activeTickets.map((ticket) => (
            <TicketCard key={ticket.id} ticket={ticket} isSelected={ticket.id === selectedTicketId} onClick={() => onSelectTicket(ticket.id)} />
          ))}
          {activeTickets.length === 0 && <p className="text-xs text-slate-500 text-center py-4">Sin incidencias activas</p>}
        </div>
      </div>
    </div>
  );
}
