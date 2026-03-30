"use client";

import { TicketSummary } from "@/types";

const priorityConfig: Record<string, { color: string; shadow: string }> = {
  critical:    { color: "#EF4444", shadow: "rgba(239,68,68,0.5)" },
  "very high": { color: "#F97316", shadow: "rgba(249,115,22,0.5)" },
  high:        { color: "#F59E0B", shadow: "rgba(245,158,11,0.5)" },
  medium:      { color: "#3B82F6", shadow: "rgba(59,130,246,0.5)" },
  low:         { color: "#10B981", shadow: "rgba(16,185,129,0.5)" },
  "very low":  { color: "#6B7280", shadow: "rgba(107,114,128,0.5)" },
};

const statusConfig: Record<string, string> = {
  open: "Pendiente",
  in_progress: "En progreso",
  delivered: "Entregado",
  resolved: "Resuelto",
  closed: "Cerrado",
};

interface Props {
  ticket: TicketSummary;
  isSelected: boolean;
  onClick: () => void;
}

export function TicketCard({ ticket, isSelected, onClick }: Props) {
  const priority = priorityConfig[ticket.priority] || priorityConfig.medium;
  const statusLabel = statusConfig[ticket.status] || ticket.status;
  const isActive = ticket.status === "in_progress";

  return (
    <div
      role="listitem"
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } }}
      tabIndex={0}
      aria-selected={isSelected}
      aria-label={`Ticket ${ticket.kosin_id}, estado ${statusLabel}`}
      className={`p-3.5 rounded-xl cursor-pointer transition-all ${
        isSelected
          ? "bg-primary/10 border border-primary/30"
          : "bg-white dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/50 hover:bg-slate-100 dark:hover:bg-slate-800/60 shadow-sm"
      }`}
    >
      <div className="flex justify-between items-start mb-2">
        <span className="text-sm font-bold text-primary">
          [ANON] {ticket.kosin_id}
        </span>
        <div className="flex gap-1">
          <span
            className={`w-1.5 h-1.5 rounded-full ${isActive ? "animate-pulse" : ""}`}
            style={{ backgroundColor: priority.color, boxShadow: `0 0 8px ${priority.shadow}` }}
            aria-hidden="true"
          />
        </div>
      </div>
      <p className={`text-xs font-medium line-clamp-2 ${isSelected ? "text-slate-600 dark:text-slate-200" : "text-slate-600 dark:text-slate-300"}`}>
        {ticket.summary}
      </p>
      <div className="mt-3 flex items-center gap-2">
        <div className="flex -space-x-2">
          <div className="w-5 h-5 rounded-full border border-white dark:border-slate-900 bg-slate-300 dark:bg-slate-700 flex items-center justify-center text-xs font-bold text-slate-500 dark:text-slate-400">
            OP
          </div>
          <div className="w-5 h-5 rounded-full border border-white dark:border-slate-900 bg-primary flex items-center justify-center text-xs font-bold text-white">
            AI
          </div>
        </div>
        <span className="text-xs text-slate-400">
          {isActive ? "Activo ahora" : statusLabel}
        </span>
      </div>
    </div>
  );
}
