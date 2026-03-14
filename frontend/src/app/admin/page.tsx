"use client";

import { useEffect, useState, useCallback } from "react";
import { API_URL } from "@/lib/config";

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

export default function AdminPage() {
  const [tickets, setTickets] = useState<AdminTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);

  const fetchTickets = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/tickets`);
      if (res.ok) {
        setTickets(await res.json());
      }
    } catch (err) {
      console.error("Failed to fetch admin tickets:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTickets();
  }, [fetchTickets]);

  const handleDelete = async (kosinKey: string) => {
    if (!confirm(`¿Eliminar el ticket ${kosinKey} de KOSIN y de la base de datos?`)) return;
    setDeleting(kosinKey);
    try {
      const res = await fetch(`${API_URL}/api/admin/tickets/${kosinKey}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setTickets((prev) => prev.filter((t) => t.kosin_ticket_id !== kosinKey));
      } else {
        const err = await res.json();
        alert(`Error al eliminar: ${err.detail || "Error desconocido"}`);
      }
    } catch (err) {
      console.error("Delete failed:", err);
      alert("Error de red al eliminar el ticket");
    } finally {
      setDeleting(null);
    }
  };

  const priorityColor: Record<string, string> = {
    critical: "bg-[#FF5630] text-white",
    high: "bg-[#FF7452] text-white",
    medium: "bg-[#FFAB00] text-[#172B4D]",
    low: "bg-[#36B37E] text-white",
  };

  const statusColor: Record<string, string> = {
    open: "bg-[#DEEBFF] text-[#0052CC]",
    in_progress: "bg-[#E3FCEF] text-[#006644]",
    resolved: "bg-[#DFE1E6] text-[#42526E]",
    closed: "bg-[#DFE1E6] text-[#6B778C]",
  };

  return (
    <div className="flex flex-col h-screen bg-[#F4F5F7]">
      {/* Header - same style as main app */}
      <header className="bg-[#0052CC] text-white h-[56px] flex items-center px-4 shrink-0 shadow-sm z-20">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-white/20 rounded flex items-center justify-center">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="white">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/>
            </svg>
          </div>
          <span className="text-[15px] font-semibold tracking-wide">
            Plataforma Anonimizacion
          </span>
        </div>

        <nav className="flex items-center gap-1 ml-8">
          <a href="/" className="px-3 py-1.5 text-[13px] font-medium text-white/70 hover:bg-white/10 rounded transition-colors">
            Incidencias
          </a>
          <span className="px-3 py-1.5 text-[13px] font-medium bg-white/20 rounded cursor-default">
            Admin
          </span>
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <button
            onClick={fetchTickets}
            className="px-2 py-1 text-[12px] text-white/70 hover:text-white hover:bg-white/10 rounded transition-colors"
            title="Refrescar"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
            </svg>
          </button>
          <div className="w-8 h-8 rounded-full bg-[#00875A] flex items-center justify-center text-[13px] font-semibold">
            OP
          </div>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-[20px] font-semibold text-[#172B4D]">
              Gestion de tickets KOSIN
            </h1>
            <span className="text-[13px] text-[#6B778C]">
              {tickets.length} ticket{tickets.length !== 1 ? "s" : ""}
            </span>
          </div>

          {loading ? (
            <div className="text-center py-12 text-[#6B778C]">Cargando...</div>
          ) : tickets.length === 0 ? (
            <div className="text-center py-12 bg-white rounded-lg border border-[#DFE1E6]">
              <p className="text-[#6B778C] text-[14px]">No hay tickets ingestados</p>
              <p className="text-[#97A0AF] text-[12px] mt-1">
                Los tickets apareceran aqui una vez ingestados desde la vista de Incidencias
              </p>
            </div>
          ) : (
            <div className="bg-white rounded-lg border border-[#DFE1E6] overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[#DFE1E6] bg-[#FAFBFC]">
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-[#6B778C] uppercase tracking-wide">KOSIN Key</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-[#6B778C] uppercase tracking-wide">Origen</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-[#6B778C] uppercase tracking-wide">Source Key</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-[#6B778C] uppercase tracking-wide">Resumen</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-[#6B778C] uppercase tracking-wide">Prioridad</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-[#6B778C] uppercase tracking-wide">Estado</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-[#6B778C] uppercase tracking-wide">Creado</th>
                    <th className="text-right px-4 py-2.5 text-[11px] font-semibold text-[#6B778C] uppercase tracking-wide">Accion</th>
                  </tr>
                </thead>
                <tbody>
                  {tickets.map((t) => (
                    <tr key={t.id} className="border-b border-[#DFE1E6] hover:bg-[#FAFBFC] transition-colors">
                      <td className="px-4 py-2.5 text-[13px] font-medium text-[#0052CC]">{t.kosin_ticket_id}</td>
                      <td className="px-4 py-2.5">
                        <span className="px-2 py-0.5 text-[11px] font-medium bg-[#DEEBFF] text-[#0052CC] rounded-full">
                          {t.source_system}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-[13px] text-[#42526E]">{t.source_ticket_id}</td>
                      <td className="px-4 py-2.5 text-[13px] text-[#172B4D] max-w-[300px] truncate">{t.summary}</td>
                      <td className="px-4 py-2.5">
                        <span className={`px-2 py-0.5 text-[11px] font-medium rounded-full ${priorityColor[t.priority] || "bg-[#DFE1E6] text-[#42526E]"}`}>
                          {t.priority}
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`px-2 py-0.5 text-[11px] font-medium rounded-full ${statusColor[t.status] || "bg-[#DFE1E6] text-[#42526E]"}`}>
                          {t.status}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-[12px] text-[#6B778C]">
                        {new Date(t.created_at).toLocaleDateString("es-ES")}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <button
                          onClick={() => handleDelete(t.kosin_ticket_id)}
                          disabled={deleting === t.kosin_ticket_id}
                          className="px-3 py-1 text-[12px] font-medium text-[#DE350B] border border-[#DE350B]/30 rounded hover:bg-[#FFEBE6] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {deleting === t.kosin_ticket_id ? "Eliminando..." : "Eliminar"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
