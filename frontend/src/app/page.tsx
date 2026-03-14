"use client";

import { useEffect, useCallback, useState, useRef } from "react";
import { useAppStore } from "@/stores/appStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import { TicketList } from "@/components/TicketList";
import { ChatPanel } from "@/components/ChatPanel";
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

  // Fetch board tickets from KOSIN
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

  // Fetch ingested tickets
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

  // Initial fetch + periodic board refresh
  useEffect(() => {
    fetchBoardTickets();
    fetchTickets();

    const interval = setInterval(fetchBoardTickets, 60000);
    return () => clearInterval(interval);
  }, [fetchBoardTickets, fetchTickets]);

  const { chatMessages } = useAppStore();

  // Select an ingested ticket → open chat
  const handleSelectTicket = useCallback(
    async (ticketId: number) => {
      selectTicket(ticketId);

      const existingMessages = chatMessages[ticketId];
      if (existingMessages && existingMessages.length > 0) {
        return;
      }

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

  // Select a board ticket → show pre-ingest state
  const handleSelectBoardTicket = useCallback(
    (key: string) => {
      selectBoardTicket(key);
    },
    [selectBoardTicket]
  );

  // Confirm ingest → anonymize + create VOLCADO → open chat
  const handleConfirmIngest = useCallback(
    async (key: string) => {
      setIsIngesting(true);
      try {
        const res = await fetch(`${API_URL}/api/tickets/ingest-confirm/${key}`, {
          method: "POST",
        });
        if (res.ok) {
          const data = await res.json();
          // Refresh both lists
          await Promise.all([fetchBoardTickets(), fetchTickets()]);
          // Select the newly ingested ticket and open chat
          handleSelectTicket(data.ticket_id);
        } else {
          const err = await res.json();
          console.error("Ingest failed:", err);
          alert(`Error al ingestar: ${err.detail || "Error desconocido"}`);
        }
      } catch (err) {
        console.error("Ingest error:", err);
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

        // If it's a chip action, register it as comment in KOSIN destination
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
        const res = await fetch(
          `${API_URL}/api/tickets/${selectedTicketId}/sync-to-client`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ comment }),
          }
        );
        if (!res.ok) {
          const err = await res.json();
          alert(`Error al sincronizar: ${err.detail || "Error desconocido"}`);
        }
      } catch (err) {
        console.error("Failed to sync to client:", err);
        alert("Error de red al sincronizar con origen");
      }
    },
    [selectedTicketId]
  );

  const handleCloseTicket = useCallback(async () => {
    if (!selectedTicketId) return;
    if (
      !confirm(
        "¿Cerrar el ticket definitivamente? El mapa de sustitución será destruido permanentemente."
      )
    )
      return;
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

  // Get the currently selected board ticket object
  const selectedBoardTicket = selectedBoardKey
    ? boardTickets.find((bt) => bt.key === selectedBoardKey) || null
    : null;

  const pendingCount = boardTickets.filter((bt) => !bt.already_ingested).length;
  const activeCount = tickets.filter((t) => t.status !== "closed").length;

  return (
    <div className="flex flex-col h-screen bg-[#F4F5F7]">
      {/* Top nav bar - Jira style */}
      <header className="bg-[#0052CC] text-white h-[56px] flex items-center px-4 shrink-0 shadow-sm z-20">
        {/* Left: Logo area */}
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

        {/* Center: Nav links */}
        <nav className="flex items-center gap-1 ml-8">
          <span className="px-3 py-1.5 text-[13px] font-medium bg-white/10 rounded cursor-default">
            Incidencias
          </span>
        </nav>

        {/* Right: User info + refresh */}
        <div className="ml-auto flex items-center gap-3">
          <button
            onClick={() => { fetchBoardTickets(); fetchTickets(); }}
            className="px-2 py-1 text-[12px] text-white/70 hover:text-white hover:bg-white/10 rounded transition-colors"
            title="Refrescar board"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
            </svg>
          </button>
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                isConnected ? "bg-[#57D9A3]" : "bg-[#FF5630]"
              }`}
            />
            <span className="text-[12px] text-white/70">
              {isConnected ? "Conectado" : "Desconectado"}
            </span>
          </div>
          <div className="w-8 h-8 rounded-full bg-[#00875A] flex items-center justify-center text-[13px] font-semibold">
            OP
          </div>
        </div>
      </header>

      {/* Secondary bar - project info */}
      <div className="bg-white border-b border-[#DFE1E6] px-4 py-2 flex items-center gap-4 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-[#0052CC] rounded-sm flex items-center justify-center">
            <span className="text-white text-[10px] font-bold">PE</span>
          </div>
          <span className="text-[13px] font-semibold text-[#172B4D]">
            Proyectos Especiales S...
          </span>
        </div>
        <span className="text-[12px] text-[#6B778C]">
          Board: {pendingCount} pendientes
        </span>
        <span className="text-[12px] text-[#6B778C]">
          En atencion: {activeCount}
        </span>
      </div>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar - Ticket list */}
        <div className="w-[340px] min-w-[280px] border-r border-[#DFE1E6] bg-white overflow-y-auto">
          <TicketList
            boardTickets={boardTickets}
            tickets={tickets}
            selectedTicketId={selectedTicketId}
            selectedBoardKey={selectedBoardKey}
            onSelectTicket={handleSelectTicket}
            onSelectBoardTicket={handleSelectBoardTicket}
          />
        </div>

        {/* Right panel - Chat or Pre-ingest */}
        <div className="flex-1 flex flex-col bg-[#F4F5F7]">
          <ChatPanel
            ticketId={selectedTicketId}
            boardTicket={selectedBoardTicket}
            onSendMessage={handleSendMessage}
            onFinishTicket={handleFinishTicket}
            onSyncToClient={handleSyncToClient}
            onCloseTicket={handleCloseTicket}
            onConfirmIngest={handleConfirmIngest}
          />
        </div>
      </div>
    </div>
  );
}
