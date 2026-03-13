"use client";

import { TicketSummary } from "@/types";

const priorityConfig: Record<string, { color: string; bg: string; label: string }> = {
  critical: { color: "#DE350B", bg: "#FFEBE6", label: "Critica" },
  high:     { color: "#FF991F", bg: "#FFF0B3", label: "Alta" },
  medium:   { color: "#0052CC", bg: "#DEEBFF", label: "Media" },
  low:      { color: "#00875A", bg: "#E3FCEF", label: "Baja" },
};

const statusConfig: Record<string, { bg: string; color: string; label: string }> = {
  open:        { bg: "#DFE1E6", color: "#42526E", label: "Pendiente" },
  in_progress: { bg: "#DEEBFF", color: "#0052CC", label: "En progreso" },
  resolved:    { bg: "#E3FCEF", color: "#00875A", label: "Resuelto" },
  closed:      { bg: "#F4F5F7", color: "#6B778C", label: "Cerrado" },
};

interface Props {
  ticket: TicketSummary;
  isSelected: boolean;
  onClick: () => void;
}

export function TicketCard({ ticket, isSelected, onClick }: Props) {
  const priority = priorityConfig[ticket.priority] || priorityConfig.medium;
  const status = statusConfig[ticket.status] || statusConfig.open;

  return (
    <div
      onClick={onClick}
      className={`px-4 py-3 border-b border-[#DFE1E6] cursor-pointer transition-all duration-100 ${
        isSelected
          ? "bg-[#E9F2FF] border-l-[3px] border-l-[#0052CC]"
          : "hover:bg-[#F4F5F7] border-l-[3px] border-l-transparent"
      }`}
    >
      {/* Top row: KOSIN ID + Priority icon */}
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          {/* Issue type icon */}
          <svg width="16" height="16" viewBox="0 0 16 16" className="shrink-0">
            <rect x="1" y="1" width="14" height="14" rx="2" fill={priority.color} opacity="0.15"/>
            <path d="M4 8h8M8 4v8" stroke={priority.color} strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <span className="text-[13px] font-medium text-[#0052CC]">
            {ticket.kosin_id}
          </span>
        </div>
        {/* Priority badge */}
        <span
          className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded"
          style={{ backgroundColor: priority.bg, color: priority.color }}
        >
          {priority.label}
        </span>
      </div>

      {/* Summary */}
      <p className="text-[13px] text-[#172B4D] leading-snug line-clamp-2 mb-2 ml-6">
        {ticket.summary}
      </p>

      {/* Bottom row: Status + date */}
      <div className="flex items-center justify-between ml-6">
        <span
          className="text-[11px] font-semibold uppercase px-2 py-0.5 rounded-sm"
          style={{ backgroundColor: status.bg, color: status.color }}
        >
          {status.label}
        </span>
        <span className="text-[11px] text-[#6B778C]">
          {new Date(ticket.created_at).toLocaleDateString("es-ES", {
            day: "2-digit",
            month: "short",
          })}
        </span>
      </div>
    </div>
  );
}
