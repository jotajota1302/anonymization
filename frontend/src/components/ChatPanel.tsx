"use client";

import { useState, useRef, useEffect } from "react";
import { useAppStore } from "@/stores/appStore";
import { ChatMessage } from "./ChatMessage";
import { BoardTicket } from "@/types";

interface Props {
  ticketId: number | null;
  boardTicket: BoardTicket | null;
  onSendMessage: (message: string, isChip?: boolean) => void;
  onFinishTicket: () => void;
  onConfirmIngest: (key: string) => void;
}

export function ChatPanel({
  ticketId,
  boardTicket,
  onSendMessage,
  onFinishTicket,
  onConfirmIngest,
}: Props) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { chatMessages, streamingContent, isStreaming, isIngesting, tickets, suggestedChips } =
    useAppStore();

  const messages = ticketId ? chatMessages[ticketId] || [] : [];
  const ticket = tickets.find((t) => t.id === ticketId);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  const handleSend = (text?: string, isChip: boolean = false) => {
    const msg = (text || input).trim();
    if (!msg || isStreaming) return;
    setInput("");
    onSendMessage(msg, isChip);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Empty state - nothing selected
  if (!ticketId && !boardTicket) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <svg className="w-20 h-20 mx-auto mb-4 text-[#C1C7D0]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1}
              d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
          </svg>
          <p className="text-[15px] font-medium text-[#6B778C]">
            Selecciona una incidencia
          </p>
          <p className="text-[12px] text-[#A5ADBA] mt-1">
            Elige un ticket del panel izquierdo para iniciar
          </p>
        </div>
      </div>
    );
  }

  // Pre-ingest state - board ticket selected but not yet ingested
  if (boardTicket && !ticketId) {
    const priorityColors: Record<string, string> = {
      Critical: "#DE350B",
      High: "#FF991F",
      Medium: "#0052CC",
      Low: "#00875A",
    };

    return (
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="bg-white border-b border-[#DFE1E6] px-6 py-4 shrink-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[13px] font-medium text-[#172B4D]">
              {boardTicket.key}
            </span>
            <span className="text-[#A5ADBA]">/</span>
            <span className="text-[11px] text-[#6B778C]">
              {boardTicket.issue_type}
            </span>
            <span className="text-[#A5ADBA]">/</span>
            <span
              className="text-[11px] font-semibold"
              style={{ color: priorityColors[boardTicket.priority] || "#0052CC" }}
            >
              {boardTicket.priority}
            </span>
          </div>
        </div>

        {/* Pre-ingest content */}
        <div className="flex-1 flex items-center justify-center px-6">
          <div className="max-w-md text-center">
            {isIngesting ? (
              /* Ingesting spinner */
              <div>
                <div className="w-16 h-16 mx-auto mb-4 border-4 border-[#DEEBFF] border-t-[#0052CC] rounded-full animate-spin" />
                <p className="text-[15px] font-semibold text-[#172B4D] mb-2">
                  Anonimizando incidencia...
                </p>
                <p className="text-[12px] text-[#6B778C]">
                  Leyendo datos, anonimizando PII y creando copia segura en KOSIN
                </p>
              </div>
            ) : (
              /* Confirm prompt */
              <div>
                <div className="w-16 h-16 mx-auto mb-4 bg-[#FFFAE6] rounded-full flex items-center justify-center">
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="#FF8B00">
                    <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/>
                  </svg>
                </div>
                <h3 className="text-[16px] font-semibold text-[#172B4D] mb-3">
                  Incidencia pendiente de atender
                </h3>

                <div className="bg-[#F4F5F7] rounded-lg p-4 mb-4 text-left">
                  <div className="text-[14px] font-semibold text-[#172B4D] mb-2">
                    {boardTicket.key}
                  </div>
                  <div className="flex gap-4 text-[12px] text-[#6B778C]">
                    <span>Tipo: <strong>{boardTicket.issue_type}</strong></span>
                    <span>Prioridad: <strong className="ml-0.5" style={{ color: priorityColors[boardTicket.priority] || "#0052CC" }}>{boardTicket.priority}</strong></span>
                  </div>
                  <div className="flex gap-4 text-[12px] text-[#6B778C] mt-1">
                    <span>Estado: <strong>{boardTicket.status}</strong></span>
                  </div>
                </div>

                <p className="text-[12px] text-[#6B778C] mb-4 leading-relaxed">
                  Al confirmar se leera la incidencia completa, se anonimizaran los datos personales
                  y se creara una copia anonimizada en KOSIN. Podras chatear con el agente IA
                  para resolverla.
                </p>

                <button
                  onClick={() => onConfirmIngest(boardTicket.key)}
                  className="px-6 py-2.5 bg-[#0052CC] text-white rounded-lg text-[14px] font-semibold
                             hover:bg-[#0747A6] active:scale-[0.98] transition-all duration-150
                             shadow-sm hover:shadow-md"
                >
                  Atender esta incidencia
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  const priorityColors: Record<string, string> = {
    critical: "#DE350B",
    high: "#FF991F",
    medium: "#0052CC",
    low: "#00875A",
  };

  const statusLabels: Record<string, string> = {
    open: "Pendiente",
    in_progress: "En progreso",
    resolved: "Resuelto",
    closed: "Cerrado",
  };

  // Show thinking indicator when streaming but no content yet
  const isThinking = isStreaming && !streamingContent;

  return (
    <div className="flex flex-col h-full">
      {/* Ticket detail header - Jira style */}
      {ticket && (
        <div className="bg-white border-b border-[#DFE1E6] px-6 py-4 shrink-0">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[13px] font-medium text-[#0052CC] hover:underline cursor-pointer">
                  {ticket.kosin_id}
                </span>
                <span className="text-[#A5ADBA]">/</span>
                <span className="text-[11px] text-[#6B778C] bg-[#DFE1E6] px-1.5 py-0.5 rounded-sm uppercase font-semibold">
                  {statusLabels[ticket.status] || ticket.status}
                </span>
              </div>
              <h2 className="text-[16px] font-semibold text-[#172B4D] leading-snug">
                {ticket.summary}
              </h2>
            </div>
            <div className="flex items-center gap-2">
              {/* Priority indicator */}
              <span
                className="w-3 h-3 rounded-sm"
                style={{ backgroundColor: priorityColors[ticket.priority] || "#0052CC" }}
                title={`Prioridad: ${ticket.priority}`}
              />
            </div>
          </div>
        </div>
      )}

      {/* Chat messages area */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.map((msg, idx) => (
          <ChatMessage key={idx} message={msg} />
        ))}

        {/* Thinking indicator */}
        {isThinking && (
          <div className="flex justify-start mb-3">
            <div className="w-8 h-8 rounded-full bg-[#0052CC] flex items-center justify-center shrink-0 mr-2 mt-1">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="white" className="animate-pulse">
                <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 110 2h-1.07A7.001 7.001 0 0113 22h-2a7.001 7.001 0 01-6.93-6H3a1 1 0 110-2h1a7 7 0 017-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 012-2z"/>
              </svg>
            </div>
            <div className="max-w-[75%] rounded-lg px-4 py-3 bg-white border border-[#DFE1E6] shadow-sm">
              <div className="text-[11px] font-semibold mb-1 uppercase tracking-wide text-[#0052CC]">
                Agente IA
              </div>
              <div className="flex items-center gap-1.5 py-1">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-[#0052CC] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-2 h-2 bg-[#0052CC] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-2 h-2 bg-[#0052CC] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
                <span className="text-[12px] text-[#6B778C] ml-1.5">Analizando...</span>
              </div>
            </div>
          </div>
        )}

        {/* Streaming content */}
        {streamingContent && (
          <div className="flex justify-start mb-3">
            <div className="w-8 h-8 rounded-full bg-[#0052CC] flex items-center justify-center shrink-0 mr-2 mt-1">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
                <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 110 2h-1.07A7.001 7.001 0 0113 22h-2a7.001 7.001 0 01-6.93-6H3a1 1 0 110-2h1a7 7 0 017-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 012-2z"/>
              </svg>
            </div>
            <div className="max-w-[75%] rounded-lg px-4 py-3 bg-white border border-[#DFE1E6] shadow-sm">
              <div className="text-[11px] font-semibold mb-1 uppercase tracking-wide text-[#0052CC]">
                Agente IA
              </div>
              <div className="text-[13px] whitespace-pre-wrap leading-relaxed text-[#172B4D]">
                {streamingContent.replace(/\[CHIPS[:\s].*?\]/gs, "").replace(/\[CHIPS[:\s].*$/s, "").trim()}
                <span className="inline-block w-1.5 h-4 bg-[#0052CC] animate-pulse ml-0.5 rounded-sm" />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested action chips */}
      {suggestedChips.length > 0 && !isStreaming && (
        <div className="px-6 py-2 bg-[#F4F5F7] border-t border-[#DFE1E6] shrink-0">
          <div className="flex gap-2 overflow-x-auto pb-1" style={{ scrollbarWidth: "none" }}>
            {suggestedChips.map((chip, i) => (
              <button
                key={i}
                onClick={() => handleSend(chip, true)}
                className="flex-shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5
                           text-[12px] font-medium text-[#0052CC] bg-[#DEEBFF] border border-[#B3D4FF]
                           rounded-full hover:bg-[#B3D4FF] hover:border-[#4C9AFF]
                           active:bg-[#4C9AFF] active:text-white active:scale-95
                           transition-all duration-150 cursor-pointer whitespace-nowrap"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" className="opacity-60">
                  <path d="M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6 1.4-1.4zm5.2 0l4.6-4.6-4.6-4.6L16 6l6 6-6 6-1.4-1.4z"/>
                </svg>
                {chip}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input area - Jira comment style */}
      <div className="bg-white border-t border-[#DFE1E6] px-6 py-4 shrink-0">
        <div className="border border-[#DFE1E6] rounded-lg focus-within:ring-2 focus-within:ring-[#4C9AFF] focus-within:border-transparent overflow-hidden">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Escribe un mensaje al agente..."
            disabled={isStreaming}
            rows={2}
            className="w-full px-4 py-3 text-[13px] text-[#172B4D] resize-none border-none
                       focus:outline-none disabled:bg-[#F4F5F7] disabled:text-[#A5ADBA]
                       placeholder:text-[#A5ADBA]"
          />
          <div className="flex items-center justify-between px-3 py-2 bg-[#F4F5F7] border-t border-[#DFE1E6]">
            {/* Action buttons */}
            <div className="flex gap-2">
              <button
                onClick={onFinishTicket}
                className="px-3 py-1.5 text-[12px] font-medium text-[#00875A] bg-[#E3FCEF] rounded
                           hover:bg-[#ABF5D1] transition-colors"
              >
                Finalizar ticket
              </button>
            </div>
            {/* Send button */}
            <button
              onClick={() => handleSend()}
              disabled={isStreaming || !input.trim()}
              className="px-4 py-1.5 bg-[#0052CC] text-white rounded text-[13px] font-medium
                         hover:bg-[#0747A6] disabled:bg-[#A5ADBA] disabled:cursor-not-allowed
                         transition-colors flex items-center gap-1.5"
            >
              <span>Enviar</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
