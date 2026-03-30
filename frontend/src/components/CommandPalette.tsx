"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useAppStore } from "@/stores/appStore";

interface CommandItem {
  id: string;
  type: "ticket" | "action" | "nav";
  label: string;
  description?: string;
  badge?: string;
  badgeColor?: string;
  href?: string;
  action?: () => void;
}

interface Props {
  onSelectTicket: (id: number) => void;
  onSelectBoardTicket: (key: string) => void;
}

const IconSearch = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
  </svg>
);
const IconTicket = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 100 4v3a2 2 0 002 2h14a2 2 0 002-2v-3a2 2 0 100-4V7a2 2 0 00-2-2H5z"/>
  </svg>
);
const IconBolt = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
  </svg>
);
const IconNav = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
  </svg>
);
const IconChevron = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="9 18 15 12 9 6"/>
  </svg>
);

export function CommandPalette({ onSelectTicket, onSelectBoardTicket }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const { tickets, boardTickets } = useAppStore();

  // Ctrl+K to open
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const buildItems = useCallback((): CommandItem[] => {
    const items: CommandItem[] = [];

    // Recent/active tickets
    const activeTickets = tickets.filter((t) => t.status !== "closed").slice(0, 5);
    activeTickets.forEach((t) => {
      items.push({
        id: `ticket-${t.id}`,
        type: "ticket",
        label: `${t.kosin_id} — ${t.summary}`,
        badge: t.status === "in_progress" ? "En progreso" : t.status === "open" ? "Pendiente" : t.status,
        badgeColor: t.status === "in_progress" ? "bg-emerald-100 text-emerald-700" : "bg-blue-100 text-blue-700",
        action: () => { onSelectTicket(t.id); setOpen(false); },
      });
    });

    // Pending board tickets
    const pending = boardTickets.filter((bt) => !bt.already_ingested).slice(0, 3);
    pending.forEach((bt) => {
      items.push({
        id: `board-${bt.key}`,
        type: "ticket",
        label: `${bt.key} — ${bt.issue_type}`,
        badge: "Pendiente ingesta",
        badgeColor: "bg-amber-100 text-amber-700",
        action: () => { onSelectBoardTicket(bt.key); setOpen(false); },
      });
    });

    // Quick actions
    items.push({
      id: "action-next",
      type: "action",
      label: "Atender siguiente ticket pendiente",
      action: () => {
        const next = boardTickets.find((bt) => !bt.already_ingested);
        if (next) { onSelectBoardTicket(next.key); }
        setOpen(false);
      },
    });

    // Navigation
    items.push(
      { id: "nav-dashboard", type: "nav", label: "Dashboard", href: "/" },
      { id: "nav-admin", type: "nav", label: "Administracion", href: "/admin" },
      { id: "nav-config", type: "nav", label: "Configuracion del sistema", href: "/config" },
    );

    return items;
  }, [tickets, boardTickets, onSelectTicket, onSelectBoardTicket]);

  const allItems = buildItems();
  const filtered = query.trim()
    ? allItems.filter((item) => item.label.toLowerCase().includes(query.toLowerCase()))
    : allItems;

  useEffect(() => { setSelectedIndex(0); }, [query]);

  // Scroll selected into view
  useEffect(() => {
    const el = listRef.current?.children[selectedIndex] as HTMLElement | undefined;
    el?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && filtered[selectedIndex]) {
      e.preventDefault();
      const item = filtered[selectedIndex];
      if (item.href) window.location.href = item.href;
      else item.action?.();
    }
  };

  if (!open) return null;

  const grouped = {
    ticket: filtered.filter((i) => i.type === "ticket"),
    action: filtered.filter((i) => i.type === "action"),
    nav: filtered.filter((i) => i.type === "nav"),
  };
  let globalIdx = -1;

  const renderItem = (item: CommandItem) => {
    globalIdx++;
    const idx = globalIdx;
    const isSelected = idx === selectedIndex;
    return (
      <div key={item.id}
        className={`flex items-center justify-between px-4 py-2.5 cursor-pointer transition-colors ${isSelected ? "bg-primary/10 text-primary" : "text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700/50"}`}
        onClick={() => { if (item.href) window.location.href = item.href; else item.action?.(); }}
        onMouseEnter={() => setSelectedIndex(idx)}
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-slate-400 shrink-0">
            {item.type === "ticket" ? <IconTicket /> : item.type === "action" ? <IconBolt /> : <IconNav />}
          </span>
          <span className="text-sm truncate">{item.label}</span>
          {item.badge && (
            <span className={`px-1.5 py-0.5 text-xs font-bold rounded shrink-0 ${item.badgeColor || "bg-slate-100 text-slate-600"}`}>
              {item.badge}
            </span>
          )}
        </div>
        <IconChevron />
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]" onClick={() => setOpen(false)}>
      {/* Backdrop */}
      <div className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm" />

      {/* Palette */}
      <div className="relative w-full max-w-lg bg-white dark:bg-slate-800 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-700 overflow-hidden" onClick={(e) => e.stopPropagation()}>
        {/* Search */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-200 dark:border-slate-700">
          <span className="text-slate-400"><IconSearch /></span>
          <input ref={inputRef} type="text" name="command-search" aria-label="Buscar tickets, acciones, navegacion" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={handleKeyDown}
            placeholder="Buscar tickets, acciones, navegacion..."
            className="flex-1 text-sm bg-transparent outline-none placeholder:text-slate-400 dark:placeholder:text-slate-500 text-slate-900 dark:text-slate-100" />
          <kbd className="px-1.5 py-0.5 text-xs font-bold text-slate-400 bg-slate-100 dark:bg-slate-700 rounded border border-slate-200 dark:border-slate-600">ESC</kbd>
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-[50vh] overflow-y-auto">
          {filtered.length === 0 && (
            <div className="py-8 text-center text-sm text-slate-400 dark:text-slate-500">Sin resultados para &quot;{query}&quot;</div>
          )}

          {grouped.ticket.length > 0 && (
            <div>
              <div className="px-4 py-2 text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest bg-slate-50 dark:bg-slate-900/50">Tickets recientes</div>
              {grouped.ticket.map(renderItem)}
            </div>
          )}

          {grouped.action.length > 0 && (
            <div>
              <div className="px-4 py-2 text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest bg-slate-50 dark:bg-slate-900/50">Acciones rapidas</div>
              {grouped.action.map(renderItem)}
            </div>
          )}

          {grouped.nav.length > 0 && (
            <div>
              <div className="px-4 py-2 text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest bg-slate-50 dark:bg-slate-900/50">Navegacion</div>
              {grouped.nav.map(renderItem)}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50 flex items-center justify-between text-xs text-slate-400 dark:text-slate-500">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <kbd className="px-1 py-0.5 bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded text-xs font-bold">↑</kbd>
              <kbd className="px-1 py-0.5 bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded text-xs font-bold">↓</kbd>
              navegar
            </span>
            <span className="flex items-center gap-1">
              <kbd className="px-1 py-0.5 bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded text-xs font-bold">↵</kbd>
              seleccionar
            </span>
          </div>
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.5 bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded text-xs font-bold">ESC</kbd>
            cerrar
          </span>
        </div>
      </div>
    </div>
  );
}
