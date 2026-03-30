"use client";

import { useEffect, useRef, useState } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useAppStore } from "@/stores/appStore";

/**
 * Mounts the WebSocket connection at layout level so it persists
 * across page navigations (incidencias <-> config).
 * Exposes sendMessage/requestSummary via appStore for page.tsx to use.
 */
export function WebSocketProvider() {
  const clientIdRef = useRef(`op-${Date.now()}`);
  const [clientId] = useState(clientIdRef.current);
  const setWsActions = useAppStore((s) => s.setWsActions);

  const { sendMessage, requestSummary } = useWebSocket(clientId);

  useEffect(() => {
    setWsActions(sendMessage, requestSummary);
  }, [sendMessage, requestSummary, setWsActions]);

  // Store clientId globally for API calls that need client_id param
  useEffect(() => {
    (window as unknown as Record<string, string>).__wsClientId = clientId;
  }, [clientId]);

  return null;
}
