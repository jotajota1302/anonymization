"use client";

import { TicketSummary, BoardTicket } from "@/types";
import { TicketCard } from "./TicketCard";

const priorityConfig: Record<string, { color: string; bg: string; label: string }> = {
  Critical: { color: "#DE350B", bg: "#FFEBE6", label: "Critica" },
  High:     { color: "#FF991F", bg: "#FFF0B3", label: "Alta" },
  Medium:   { color: "#0052CC", bg: "#DEEBFF", label: "Media" },
  Low:      { color: "#00875A", bg: "#E3FCEF", label: "Baja" },
};

const statusConfig: Record<string, { bg: string; color: string }> = {
  Open:          { bg: "#DFE1E6", color: "#42526E" },
  "In Progress": { bg: "#DEEBFF", color: "#0052CC" },
  "To Do":       { bg: "#DFE1E6", color: "#42526E" },
};

interface Props {
  boardTickets: BoardTicket[];
  tickets: TicketSummary[];
  selectedTicketId: number | null;
  selectedBoardKey: string | null;
  onSelectTicket: (id: number) => void;
  onSelectBoardTicket: (key: string) => void;
}

export function TicketList({
  boardTickets,
  tickets,
  selectedTicketId,
  selectedBoardKey,
  onSelectTicket,
  onSelectBoardTicket,
}: Props) {
  const pendingBoard = boardTickets.filter((bt) => !bt.already_ingested);
  const activeTickets = tickets.filter((t) => t.status !== "closed");

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#DFE1E6]">
        <div className="flex items-center justify-between">
          <h2 className="text-[13px] font-semibold text-[#172B4D] uppercase tracking-wide">
            Incidencias
          </h2>
          <span className="text-[12px] text-[#6B778C] bg-[#DFE1E6] px-2 py-0.5 rounded-full font-medium">
            {pendingBoard.length + activeTickets.length}
          </span>
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {/* Section: Pending board tickets */}
        {pendingBoard.length > 0 && (
          <>
            <div className="px-4 py-2 bg-[#FFFAE6] border-b border-[#DFE1E6]">
              <div className="flex items-center gap-2">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="#FF8B00">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                </svg>
                <span className="text-[11px] font-semibold text-[#172B4D] uppercase tracking-wider">
                  Pendientes
                </span>
                <span className="text-[10px] text-[#6B778C] bg-[#FFF0B3] px-1.5 py-0.5 rounded-full font-medium">
                  {pendingBoard.length}
                </span>
              </div>
            </div>
            {pendingBoard.map((bt) => {
              const priority = priorityConfig[bt.priority] || priorityConfig.Medium;
              const status = statusConfig[bt.status] || statusConfig.Open;
              const isSelected = bt.key === selectedBoardKey;

              return (
                <div
                  key={bt.key}
                  onClick={() => onSelectBoardTicket(bt.key)}
                  className={`px-4 py-3 border-b border-[#DFE1E6] cursor-pointer transition-all duration-100 ${
                    isSelected
                      ? "bg-[#FFFAE6] border-l-[3px] border-l-[#FF8B00]"
                      : "hover:bg-[#F4F5F7] border-l-[3px] border-l-transparent"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <svg width="16" height="16" viewBox="0 0 16 16" className="shrink-0">
                        <rect x="1" y="1" width="14" height="14" rx="2" fill={priority.color} opacity="0.15"/>
                        <path d="M4 8h8M8 4v8" stroke={priority.color} strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                      <span className="text-[13px] font-medium text-[#172B4D]">
                        {bt.key}
                      </span>
                    </div>
                    <span
                      className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded"
                      style={{ backgroundColor: priority.bg, color: priority.color }}
                    >
                      {priority.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 ml-6">
                    <span
                      className="text-[10px] font-medium px-1.5 py-0.5 rounded-sm"
                      style={{ backgroundColor: status.bg, color: status.color }}
                    >
                      {bt.status}
                    </span>
                    <span className="text-[10px] text-[#6B778C]">
                      {bt.issue_type}
                    </span>
                  </div>
                </div>
              );
            })}
          </>
        )}

        {/* Section: Ingested / Active tickets */}
        {activeTickets.length > 0 && (
          <>
            <div className="px-4 py-2 bg-[#E3FCEF] border-b border-[#DFE1E6]">
              <div className="flex items-center gap-2">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="#00875A">
                  <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                </svg>
                <span className="text-[11px] font-semibold text-[#172B4D] uppercase tracking-wider">
                  En atencion
                </span>
                <span className="text-[10px] text-[#6B778C] bg-[#ABF5D1] px-1.5 py-0.5 rounded-full font-medium">
                  {activeTickets.length}
                </span>
              </div>
            </div>
            {activeTickets.map((ticket) => (
              <TicketCard
                key={ticket.id}
                ticket={ticket}
                isSelected={ticket.id === selectedTicketId}
                onClick={() => onSelectTicket(ticket.id)}
              />
            ))}
          </>
        )}

        {/* Empty state */}
        {pendingBoard.length === 0 && activeTickets.length === 0 && (
          <div className="p-6 text-center text-[#6B778C] text-[13px]">
            <svg className="w-12 h-12 mx-auto mb-3 text-[#DFE1E6]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            No hay incidencias disponibles.
          </div>
        )}
      </div>
    </div>
  );
}
