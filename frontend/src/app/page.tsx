"use client";

import { useEffect, useCallback, useState, useRef } from "react";
import { useAppStore } from "@/stores/appStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import { TicketList } from "@/components/TicketList";
import { ChatPanel } from "@/components/ChatPanel";
import { CommandPalette } from "@/components/CommandPalette";
import { Header } from "@/components/Header";
import { API_URL } from "@/lib/config";
import { TicketSummary, BoardTicket } from "@/types";

export default function Home() {
  const {
    tickets,
    boardTickets,
    setTickets,
    setBoardTickets,
    selectedTicketId,
    selectedBoardKey,
    selectTicket,
    selectBoardTicket,
    setChatHistory,
    isConnected,
    isIngesting,
    setIsIngesting,
  } = useAppStore();

  // Toast notification state
  const [toast, setToast] = useState<{ message: string; type: "error" | "success" } | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout>>();

  const showToast = useCallback((message: string, type: "error" | "success" = "error") => {
    setToast({ message, type });
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 6000);
  }, []);

  // Confirm modal state (replaces native confirm())
  const [confirmModal, setConfirmModal] = useState<{ title: string; message: string; onConfirm: () => void } | null>(null);

  const clientIdRef = useRef<string>("");
  const [clientId, setClientId] = useState("operator");

  useEffect(() => {
    clientIdRef.current = `op-${Date.now()}`;
    setClientId(clientIdRef.current);
  }, []);

  const { sendMessage, requestSummary } = useWebSocket(clientId);

  const fetchBoardTickets = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/tickets/board`);
      if (res.ok) {
        const data: BoardTicket[] = await res.json();
        setBoardTickets(data);
      }
    } catch (err) {
      console.error("Failed to fetch board tickets:", err);
    }
  }, [setBoardTickets]);

  const fetchTickets = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/tickets`);
      if (res.ok) {
        const data: TicketSummary[] = await res.json();
        setTickets(data);
      }
    } catch (err) {
      console.error("Failed to fetch tickets:", err);
    }
  }, [setTickets]);

  const [pollingMs, setPollingMs] = useState(60000);

  useEffect(() => {
    fetch(`${API_URL}/api/config/general`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data?.polling_interval_sec) setPollingMs(data.polling_interval_sec * 1000);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchBoardTickets();
    fetchTickets();
    const interval = setInterval(fetchBoardTickets, pollingMs);
    return () => clearInterval(interval);
  }, [fetchBoardTickets, fetchTickets, pollingMs]);

  const { chatMessages } = useAppStore();

  const handleSelectTicket = useCallback(
    async (ticketId: number) => {
      selectTicket(ticketId);
      const existingMessages = chatMessages[ticketId];
      if (existingMessages && existingMessages.length > 0) return;
      try {
        const res = await fetch(`${API_URL}/api/tickets/${ticketId}`);
        if (res.ok) {
          const data = await res.json();
          if (data.chat_history?.length > 0) {
            setChatHistory(ticketId, data.chat_history);
          } else {
            requestSummary(ticketId);
          }
        }
      } catch (err) {
        console.error("Failed to load ticket detail:", err);
      }
    },
    [selectTicket, setChatHistory, requestSummary, chatMessages]
  );

  // Auto-select ticket from query param (e.g. /?ticket=5)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ticketParam = params.get("ticket");
    if (ticketParam && tickets.length > 0) {
      const id = Number(ticketParam);
      if (id && tickets.some((t) => t.id === id) && selectedTicketId !== id) {
        handleSelectTicket(id);
        // Clean up URL
        window.history.replaceState({}, "", "/");
      }
    }
  }, [tickets, handleSelectTicket, selectedTicketId]);

  const handleSelectBoardTicket = useCallback(
    (key: string) => { selectBoardTicket(key); },
    [selectBoardTicket]
  );

  const handleConfirmIngest = useCallback(
    async (key: string) => {
      setIsIngesting(true);
      try {
        const res = await fetch(`${API_URL}/api/tickets/ingest-confirm/${key}`, { method: "POST" });
        if (res.ok) {
          const data = await res.json();
          if (data.pii_warning) {
            showToast(data.pii_warning, "success");
          }
          await Promise.all([fetchBoardTickets(), fetchTickets()]);
          handleSelectTicket(data.ticket_id);
        } else {
          const err = await res.json();
          showToast(`Error al ingestar: ${err.detail || "Error desconocido"}`);
        }
      } catch (err) {
        showToast("Error de red al ingestar el ticket");
      } finally {
        setIsIngesting(false);
      }
    },
    [setIsIngesting, fetchBoardTickets, fetchTickets, handleSelectTicket]
  );

  const handleSendMessage = useCallback(
    (message: string, isChip: boolean = false) => {
      if (selectedTicketId) {
        sendMessage(selectedTicketId, message);
        if (isChip) {
          fetch(`${API_URL}/api/tickets/${selectedTicketId}/kosin-comment`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: message }),
          }).catch((err) => console.error("Failed to register action in KOSIN:", err));
        }
      }
    },
    [selectedTicketId, sendMessage]
  );

  const handleFinishTicket = useCallback(async () => {
    if (!selectedTicketId) return;
    try {
      await fetch(`${API_URL}/api/tickets/${selectedTicketId}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "resolved" }),
      });
      fetchTickets();
    } catch (err) {
      console.error("Failed to finish ticket:", err);
    }
  }, [selectedTicketId, fetchTickets]);

  const handleSyncToClient = useCallback(
    async (comment: string) => {
      if (!selectedTicketId) return;
      try {
        const res = await fetch(`${API_URL}/api/tickets/${selectedTicketId}/sync-to-client`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ comment }),
        });
        if (!res.ok) {
          const err = await res.json();
          showToast(`Error al sincronizar: ${err.detail || "Error desconocido"}`);
        }
      } catch (err) {
        showToast("Error de red al sincronizar con origen");
      }
    },
    [selectedTicketId]
  );

  const doCloseTicket = useCallback(async () => {
    if (!selectedTicketId) return;
    try {
      await fetch(`${API_URL}/api/tickets/${selectedTicketId}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "closed" }),
      });
      fetchTickets();
    } catch (err) {
      console.error("Failed to close ticket:", err);
    }
  }, [selectedTicketId, fetchTickets]);

  const handleCloseTicket = useCallback(() => {
    if (!selectedTicketId) return;
    setConfirmModal({
      title: "Cerrar ticket definitivamente",
      message: "El mapa de sustitucion sera destruido permanentemente. Esta accion no se puede deshacer.",
      onConfirm: () => { doCloseTicket(); setConfirmModal(null); },
    });
  }, [selectedTicketId, doCloseTicket]);

  const selectedBoardTicket = selectedBoardKey
    ? boardTickets.find((bt) => bt.key === selectedBoardKey) || null
    : null;

  return (
    <div className="bg-[#F8FAFC] dark:bg-slate-900 text-slate-900 dark:text-slate-100 h-screen flex flex-col overflow-hidden">
      <Header
        activePage="incidencias"
        isConnected={isConnected}
        subheader={
          <>
            <div className="flex items-center gap-3 text-sm font-medium">
              <span className="text-slate-400 dark:text-slate-400">KOSIN</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-slate-400"><polyline points="9 18 15 12 9 6"/></svg>
              <span className="text-slate-700 dark:text-slate-100">Proyecto PESESG</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest mr-2">Sistemas Integrados:</span>
              <div className="flex gap-1.5">
                {[...new Set(boardTickets.map((bt) => bt.source_system))].map((src) => (
                  <span key={src} className="px-2 py-0.5 bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-300 text-xs font-bold rounded border border-slate-300 dark:border-slate-700">
                    {src.toUpperCase()}
                  </span>
                ))}
                {boardTickets.length === 0 && (
                  <span className="text-xs text-slate-400 dark:text-slate-500 italic">ninguno</span>
                )}
              </div>
            </div>
          </>
        }
      />

      {/* Main Content */}
      <main className="flex-1 flex min-h-0 overflow-hidden">
        <aside className="w-[30%] bg-slate-50 dark:bg-slate-950 flex flex-col border-r border-slate-200 dark:border-slate-700 min-h-0" aria-label="Lista de incidencias">
          <TicketList
            boardTickets={boardTickets} tickets={tickets}
            selectedTicketId={selectedTicketId} selectedBoardKey={selectedBoardKey}
            onSelectTicket={handleSelectTicket} onSelectBoardTicket={handleSelectBoardTicket}
          />
        </aside>
        <section id="main-content" className="flex-1 flex flex-col min-h-0 bg-white dark:bg-slate-900">
          <ChatPanel
            ticketId={selectedTicketId} boardTicket={selectedBoardTicket}
            onSendMessage={handleSendMessage} onFinishTicket={handleFinishTicket}
            onSyncToClient={handleSyncToClient} onCloseTicket={handleCloseTicket}
            onConfirmIngest={handleConfirmIngest}
          />
        </section>
      </main>

      {/* Command Palette (Ctrl+K) */}
      <CommandPalette onSelectTicket={handleSelectTicket} onSelectBoardTicket={handleSelectBoardTicket} />

      {/* Toast notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-4 fade-in duration-300">
          <div className={`flex items-center gap-3 px-5 py-3 rounded-lg shadow-lg border text-sm font-medium ${
            toast.type === "error"
              ? "bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-800 text-red-800 dark:text-red-300"
              : "bg-green-50 dark:bg-green-900/30 border-green-200 dark:border-green-800 text-green-800 dark:text-green-300"
          }`}>
            <span>{toast.type === "error" ? "\u26A0" : "\u2713"}</span>
            <span>{toast.message}</span>
            <button onClick={() => setToast(null)} className="ml-2 text-current opacity-50 hover:opacity-100">&times;</button>
          </div>
        </div>
      )}

      {/* Confirm modal */}
      {confirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl p-6 max-w-md w-full mx-4 border border-slate-200 dark:border-slate-700">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#EF4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                  <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
              </div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">{confirmModal.title}</h3>
            </div>
            <p className="text-sm text-slate-600 dark:text-slate-400 mb-6 ml-[52px]">{confirmModal.message}</p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setConfirmModal(null)} className="px-4 py-2 text-sm font-bold text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-700 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors">
                Cancelar
              </button>
              <button onClick={confirmModal.onConfirm} className="px-4 py-2 text-sm font-bold text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors">
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
