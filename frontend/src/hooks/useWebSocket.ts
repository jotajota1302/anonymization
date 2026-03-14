"use client";

import { useEffect, useRef, useCallback } from "react";
import { WS_URL } from "@/lib/config";
import { useAppStore } from "@/stores/appStore";
import { WSMessage } from "@/types";

const RECONNECT_INTERVALS = [1000, 2000, 4000, 8000, 16000];
const PING_INTERVAL = 30000;

export function useWebSocket(clientId: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempt = useRef(0);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const {
    setIsConnected,
    appendToken,
    clearStreaming,
    setIsStreaming,
    addMessage,
    selectedTicketId,
    setSuggestedChips,
  } = useAppStore();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(`${WS_URL}/ws/chat/${clientId}`);

    ws.onopen = () => {
      setIsConnected(true);
      reconnectAttempt.current = 0;

      // Start ping keepalive
      pingIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ action: "ping" }));
        }
      }, PING_INTERVAL);
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);

        switch (msg.type) {
          case "token":
            appendToken(msg.data);
            setIsStreaming(true);
            break;

          case "complete": {
            let content = msg.data;
            let chips: string[] = [];

            // Parse [CHIPS: "a", "b", "c"] from response
            // Use greedy match to handle tokens like [PERSONA_1] inside chip text
            const chipsMatch = content.match(/\[CHIPS[:\s]\s*(.*)\](?!.*\])/s);
            if (chipsMatch && chipsMatch[1]) {
              // Extract quoted strings (supports straight and curly quotes)
              const quotePattern = /[""\u201C\u201D]([^""\u201C\u201D]+)[""\u201C\u201D]/g;
              let m: RegExpExecArray | null;
              while ((m = quotePattern.exec(chipsMatch[1])) !== null) {
                // Skip chips that contain redacted PII tokens
                const chipText = m[1];
                if (/\[[A-Z_]+REDACTED\]|\[[A-Z_]+_\d+\]/.test(chipText)) continue;
                chips.push(chipText);
              }
              content = content.slice(0, content.indexOf(chipsMatch[0])).trim();
            }
            // Strip any remaining CHIPS patterns
            content = content.replace(/\[CHIPS[:\s].*$/s, "").trim();

            if (msg.ticket_id) {
              addMessage(msg.ticket_id, {
                role: "agent",
                content,
                timestamp: new Date().toISOString(),
              });
            }
            setSuggestedChips(chips);
            clearStreaming();
            break;
          }

          case "error":
            console.error("WS error:", msg.data);
            if (msg.ticket_id) {
              addMessage(msg.ticket_id, {
                role: "agent",
                content: `Error: ${msg.data}`,
                timestamp: new Date().toISOString(),
              });
            }
            clearStreaming();
            break;

          case "info":
            // Info messages (e.g., tool execution status)
            break;
        }
      } catch (e) {
        console.error("Failed to parse WS message:", e);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }

      // Reconnect with exponential backoff
      const delay =
        RECONNECT_INTERVALS[
          Math.min(reconnectAttempt.current, RECONNECT_INTERVALS.length - 1)
        ];
      reconnectAttempt.current++;
      setTimeout(connect, delay);
    };

    ws.onerror = () => {
      // Connection errors handled by onclose/reconnect
    };

    wsRef.current = ws;
  }, [clientId, setIsConnected, appendToken, clearStreaming, setIsStreaming, addMessage, setSuggestedChips]);

  const sendMessage = useCallback(
    (ticketId: number, message: string) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        // Add operator message to store immediately
        addMessage(ticketId, {
          role: "operator",
          content: message,
          timestamp: new Date().toISOString(),
        });

        setSuggestedChips([]);
        wsRef.current.send(
          JSON.stringify({
            ticket_id: ticketId,
            message,
            action: "chat",
          })
        );
        setIsStreaming(true);
      }
    },
    [addMessage, setIsStreaming]
  );

  const requestSummary = useCallback(
    (ticketId: number) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            ticket_id: ticketId,
            action: "summary",
          })
        );
        setIsStreaming(true);
      }
    },
    [setIsStreaming]
  );

  useEffect(() => {
    connect();
    return () => {
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { sendMessage, requestSummary };
}
