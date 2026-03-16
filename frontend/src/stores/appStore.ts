import { create } from "zustand";
import { TicketSummary, ChatMessage, BoardTicket } from "@/types";

interface AppState {
  tickets: TicketSummary[];
  boardTickets: BoardTicket[];
  selectedTicketId: number | null;
  selectedBoardKey: string | null;
  chatMessages: Record<number, ChatMessage[]>;
  streamingContent: string;
  isStreaming: boolean;
  isConnected: boolean;
  isIngesting: boolean;
  isLoadingBoard: boolean;
  isLoadingTickets: boolean;
  piiWarnings: Record<number, string>;
  suggestedChips: string[];

  setTickets: (tickets: TicketSummary[]) => void;
  setBoardTickets: (tickets: BoardTicket[]) => void;
  selectTicket: (id: number | null) => void;
  selectBoardTicket: (key: string | null) => void;
  addMessage: (ticketId: number, msg: ChatMessage) => void;
  setChatHistory: (ticketId: number, messages: ChatMessage[]) => void;
  appendToken: (token: string) => void;
  clearStreaming: () => void;
  setIsStreaming: (val: boolean) => void;
  setIsConnected: (val: boolean) => void;
  setIsIngesting: (val: boolean) => void;
  setIsLoadingBoard: (val: boolean) => void;
  setIsLoadingTickets: (val: boolean) => void;
  setPiiWarning: (ticketId: number, warning: string) => void;
  setSuggestedChips: (chips: string[]) => void;
  updateTicketStatus: (ticketId: number, status: TicketSummary["status"]) => void;
}

export const useAppStore = create<AppState>((set) => ({
  tickets: [],
  boardTickets: [],
  selectedTicketId: null,
  selectedBoardKey: null,
  chatMessages: {},
  streamingContent: "",
  isStreaming: false,
  isConnected: false,
  isIngesting: false,
  isLoadingBoard: true,
  isLoadingTickets: true,
  piiWarnings: {},
  suggestedChips: [],

  setTickets: (tickets) => set({ tickets }),

  setBoardTickets: (boardTickets) => set({ boardTickets }),

  selectTicket: (id) => set({ selectedTicketId: id, selectedBoardKey: null, streamingContent: "", suggestedChips: [] }),

  selectBoardTicket: (key) => set({ selectedBoardKey: key, selectedTicketId: null, streamingContent: "", suggestedChips: [] }),

  addMessage: (ticketId, msg) =>
    set((state) => ({
      chatMessages: {
        ...state.chatMessages,
        [ticketId]: [...(state.chatMessages[ticketId] || []), msg],
      },
    })),

  setChatHistory: (ticketId, messages) =>
    set((state) => ({
      chatMessages: {
        ...state.chatMessages,
        [ticketId]: messages,
      },
    })),

  appendToken: (token) =>
    set((state) => ({
      streamingContent: state.streamingContent + token,
    })),

  clearStreaming: () => set({ streamingContent: "", isStreaming: false }),

  setSuggestedChips: (chips) => set({ suggestedChips: chips }),

  setIsStreaming: (val) => set({ isStreaming: val }),

  setIsConnected: (val) => set({ isConnected: val }),

  setIsIngesting: (val) => set({ isIngesting: val }),

  setIsLoadingBoard: (val) => set({ isLoadingBoard: val }),

  setIsLoadingTickets: (val) => set({ isLoadingTickets: val }),

  setPiiWarning: (ticketId, warning) =>
    set((state) => ({
      piiWarnings: { ...state.piiWarnings, [ticketId]: warning },
    })),

  updateTicketStatus: (ticketId, status) =>
    set((state) => ({
      tickets: state.tickets.map((t) =>
        t.id === ticketId ? { ...t, status } : t
      ),
    })),
}));
