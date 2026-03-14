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
          await Promise.all([fetchBoardTickets(), fetchTickets()]);
          handleSelectTicket(data.ticket_id);
        } else {
          const err = await res.json();
          alert(`Error al ingestar: ${err.detail || "Error desconocido"}`);
        }
      } catch (err) {
        alert("Error de red al ingestar el ticket");
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
          alert(`Error al sincronizar: ${err.detail || "Error desconocido"}`);
        }
      } catch (err) {
        alert("Error de red al sincronizar con origen");
      }
    },
    [selectedTicketId]
  );

  const handleCloseTicket = useCallback(async () => {
    if (!selectedTicketId) return;
    if (!confirm("¿Cerrar el ticket definitivamente? El mapa de sustitucion sera destruido permanentemente.")) return;
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

  const selectedBoardTicket = selectedBoardKey
    ? boardTickets.find((bt) => bt.key === selectedBoardKey) || null
    : null;

  return (
    <div className="bg-[#F8FAFC] text-slate-900 min-h-screen flex flex-col overflow-hidden">
      <Header
        activePage="incidencias"
        isConnected={isConnected}
        subheader={
          <>
            <div className="flex items-center gap-3 text-sm font-medium">
              <span className="text-slate-400">KOSIN</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#475569" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
              <span className="text-slate-100">Proyecto PESESG</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mr-2">Sistemas Integrados:</span>
              <div className="flex gap-1.5">
                {[...new Set(boardTickets.map((bt) => bt.source_system))].map((src) => (
                  <span key={src} className="px-2 py-0.5 bg-slate-800 text-slate-300 text-[11px] font-semibold rounded border border-slate-700">
                    {src.toUpperCase()}
                  </span>
                ))}
                {boardTickets.length === 0 && (
                  <span className="text-[11px] text-slate-500 italic">ninguno</span>
                )}
              </div>
            </div>
          </>
        }
      />

      {/* Main Content */}
      <main className="flex-1 flex overflow-hidden">
        <aside className="w-[30%] bg-navy-deep flex flex-col border-r border-slate-800 overflow-y-auto custom-scrollbar" aria-label="Lista de incidencias">
          <TicketList
            boardTickets={boardTickets} tickets={tickets}
            selectedTicketId={selectedTicketId} selectedBoardKey={selectedBoardKey}
            onSelectTicket={handleSelectTicket} onSelectBoardTicket={handleSelectBoardTicket}
          />
        </aside>
        <section id="main-content" className="flex-1 flex flex-col bg-white">
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
    </div>
  );
}
