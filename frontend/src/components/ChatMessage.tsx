"use client";

import { ChatMessage as ChatMessageType } from "@/types";

interface Props {
  message: ChatMessageType;
}

/**
 * Renders message content, converting KOSIN ticket references and URLs into clickable links.
 * Patterns detected:
 * - PESESG-XXX -> link to KOSIN
 * - [LINK:url:label] -> clickable link with label
 */
function renderContent(text: string) {
  // Strip [CHIPS:...] from displayed content
  // Greedy match from [CHIPS to the LAST ] to handle nested tokens like [PERSONA_1]
  text = text.replace(/\[CHIPS[:\s].*\](?!.*\])/gs, "").replace(/\[CHIPS[:\s].*$/s, "").trim();

  // Pattern for explicit links: [LINK:url:label]
  // Pattern for KOSIN ticket refs: PESESG-\d+
  const KOSIN_BASE = "https://umane.emeal.nttdata.com/jiraito/browse";
  const pattern = /(\[LINK:(.*?):(.*?)\])|(PESESG-\d+)/g;

  const parts: (string | JSX.Element)[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    // Add text before match
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    if (match[1]) {
      // [LINK:url:label] pattern
      const url = match[2];
      const label = match[3];
      parts.push(
        <a
          key={match.index}
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-[#0052CC] hover:text-[#0747A6] underline font-medium"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" className="shrink-0">
            <path d="M19 19H5V5h7V3H5a2 2 0 00-2 2v14a2 2 0 002 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/>
          </svg>
          {label}
        </a>
      );
    } else if (match[4]) {
      // PESESG-XXX pattern
      const ticketKey = match[4];
      parts.push(
        <a
          key={match.index}
          href={`${KOSIN_BASE}/${ticketKey}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-[#0052CC] hover:text-[#0747A6] underline font-medium"
        >
          <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" className="shrink-0 opacity-70">
            <path d="M19 19H5V5h7V3H5a2 2 0 00-2 2v14a2 2 0 002 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/>
          </svg>
          {ticketKey}
        </a>
      );
    }

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : text;
}

export function ChatMessage({ message }: Props) {
  const isAgent = message.role === "agent";

  return (
    <div className={`flex ${isAgent ? "justify-start" : "justify-end"} mb-3`}>
      {/* Avatar */}
      {isAgent && (
        <div className="w-8 h-8 rounded-full bg-[#0052CC] flex items-center justify-center shrink-0 mr-2 mt-1">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
            <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 110 2h-1.07A7.001 7.001 0 0113 22h-2a7.001 7.001 0 01-6.93-6H3a1 1 0 110-2h1a7 7 0 017-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 012-2z"/>
          </svg>
        </div>
      )}

      <div
        className={`max-w-[75%] rounded-lg px-4 py-3 ${
          isAgent
            ? "bg-white border border-[#DFE1E6] shadow-sm"
            : "bg-[#0052CC] text-white"
        }`}
      >
        <div className={`text-[11px] font-semibold mb-1 uppercase tracking-wide ${
          isAgent ? "text-[#0052CC]" : "text-white/80"
        }`}>
          {isAgent ? "Agente IA" : "Operador"}
        </div>
        <div className={`text-[13px] whitespace-pre-wrap leading-relaxed ${
          isAgent ? "text-[#172B4D]" : "text-white"
        }`}>
          {isAgent ? renderContent(message.content) : message.content}
        </div>
        <div className={`text-[10px] mt-2 text-right ${
          isAgent ? "text-[#A5ADBA]" : "text-white/50"
        }`}>
          {new Date(message.timestamp).toLocaleTimeString("es-ES", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      </div>

      {/* Avatar for operator */}
      {!isAgent && (
        <div className="w-8 h-8 rounded-full bg-[#00875A] flex items-center justify-center shrink-0 ml-2 mt-1">
          <span className="text-white text-[11px] font-bold">OP</span>
        </div>
      )}
    </div>
  );
}
