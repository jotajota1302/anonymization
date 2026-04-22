"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import Link from "next/link";
import { Header } from "@/components/Header";
import { API_URL } from "@/lib/config";
import type { TicketSummary, BoardTicket, IntegrationConfig } from "@/types";

const cardCls =
  "bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm";

const STATUS_META: Record<
  TicketSummary["status"],
  { label: string; color: string; bar: string; ring: string }
> = {
  open: {
    label: "Abierto",
    color: "text-blue-700 dark:text-blue-300",
    bar: "bg-blue-500",
    ring: "ring-blue-500/20",
  },
  in_progress: {
    label: "En progreso",
    color: "text-emerald-700 dark:text-emerald-300",
    bar: "bg-emerald-500",
    ring: "ring-emerald-500/20",
  },
  delivered: {
    label: "Entregado",
    color: "text-indigo-700 dark:text-indigo-300",
    bar: "bg-indigo-500",
    ring: "ring-indigo-500/20",
  },
  resolved: {
    label: "Resuelto",
    color: "text-amber-700 dark:text-amber-300",
    bar: "bg-amber-500",
    ring: "ring-amber-500/20",
  },
  closed: {
    label: "Cerrado",
    color: "text-slate-600 dark:text-slate-300",
    bar: "bg-slate-400 dark:bg-slate-500",
    ring: "ring-slate-500/20",
  },
};

const PRIORITY_META: Record<
  string,
  { label: string; bar: string; text: string }
> = {
  critical: { label: "Critica", bar: "bg-red-500", text: "text-red-700 dark:text-red-300" },
  "very high": { label: "Muy alta", bar: "bg-red-400", text: "text-red-700 dark:text-red-300" },
  high: { label: "Alta", bar: "bg-amber-500", text: "text-amber-700 dark:text-amber-300" },
  medium: { label: "Media", bar: "bg-blue-500", text: "text-blue-700 dark:text-blue-300" },
  low: { label: "Baja", bar: "bg-emerald-500", text: "text-emerald-700 dark:text-emerald-300" },
  "very low": { label: "Muy baja", bar: "bg-emerald-400", text: "text-emerald-700 dark:text-emerald-300" },
};

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 5) return "Ahora mismo";
  if (secs < 60) return `Hace ${secs}s`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `Hace ${mins} min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `Hace ${hours}h`;
  const days = Math.floor(hours / 24);
  return `Hace ${days}d`;
}

/** Horizontal bar with label + count. */
function BarRow({
  label,
  count,
  total,
  barClass,
  labelClass,
}: {
  label: string;
  count: number;
  total: number;
  barClass: string;
  labelClass?: string;
}) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  return (
    <div className="flex items-center gap-3">
      <div className={`w-28 text-xs font-semibold shrink-0 ${labelClass ?? "text-slate-700 dark:text-slate-300"}`}>
        {label}
      </div>
      <div className="flex-1 h-2.5 bg-slate-100 dark:bg-slate-700/60 rounded-full overflow-hidden">
        <div
          className={`h-full ${barClass} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="w-14 text-right text-xs font-bold text-slate-900 dark:text-slate-100 shrink-0 tabular-nums">
        {count} <span className="text-slate-400 font-medium">· {pct}%</span>
      </div>
    </div>
  );
}

/** Donut chart rendered as concentric SVG arcs. */
function Donut({
  segments,
  size = 180,
  stroke = 22,
  centerLabel,
  centerSub,
}: {
  segments: { value: number; color: string; label: string }[];
  size?: number;
  stroke?: number;
  centerLabel: string;
  centerSub: string;
}) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const total = segments.reduce((acc, s) => acc + s.value, 0);

  let offset = 0;
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          className="text-slate-100 dark:text-slate-700/60"
        />
        {total > 0 &&
          segments.map((seg, i) => {
            if (seg.value === 0) return null;
            const dash = (seg.value / total) * circumference;
            const circle = (
              <circle
                key={i}
                cx={size / 2}
                cy={size / 2}
                r={radius}
                fill="none"
                stroke={seg.color}
                strokeWidth={stroke}
                strokeDasharray={`${dash} ${circumference - dash}`}
                strokeDashoffset={-offset}
                strokeLinecap="butt"
              />
            );
            offset += dash;
            return circle;
          })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="text-3xl font-bold text-slate-900 dark:text-slate-100 tabular-nums">
          {centerLabel}
        </div>
        <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 mt-0.5 uppercase tracking-wider">
          {centerSub}
        </div>
      </div>
    </div>
  );
}

function KpiCard({
  label,
  value,
  sub,
  accent,
  icon,
  href,
}: {
  label: string;
  value: number | string;
  sub?: string;
  accent: string;
  icon: React.ReactNode;
  href?: string;
}) {
  const inner = (
    <div className={`${cardCls} p-5 relative overflow-hidden group transition-all hover:shadow-md ${href ? "cursor-pointer" : ""}`}>
      <div className={`absolute top-0 left-0 right-0 h-1 ${accent}`} />
      <div className="flex items-start justify-between mb-3">
        <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
          {label}
        </span>
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${accent} bg-opacity-15 text-white`}>
          {icon}
        </div>
      </div>
      <div className="text-4xl font-bold text-slate-900 dark:text-slate-100 tabular-nums">
        {value}
      </div>
      {sub && (
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-1.5 font-medium">{sub}</div>
      )}
    </div>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
}

// --- Icons ---
const IconAttention = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
  </svg>
);
const IconCheckCircle = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
  </svg>
);
const IconArchive = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="21 8 21 21 3 21 3 8" /><rect x="1" y="3" width="22" height="5" /><line x1="10" y1="12" x2="14" y2="12" />
  </svg>
);
const IconInbox = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 12 16 12 14 15 10 15 8 12 2 12" /><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
  </svg>
);
const IconRefresh = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" /><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </svg>
);

export default function DashboardPage() {
  const [tickets, setTickets] = useState<TicketSummary[]>([]);
  const [boardTickets, setBoardTickets] = useState<BoardTicket[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const fetchAll = useCallback(async () => {
    try {
      const [ticketsRes, boardRes, integrationsRes] = await Promise.all([
        fetch(`${API_URL}/api/tickets`).then((r) => (r.ok ? r.json() : [])),
        fetch(`${API_URL}/api/tickets/board`).then((r) => (r.ok ? r.json() : [])),
        fetch(`${API_URL}/api/config/integrations`).then((r) => (r.ok ? r.json() : [])),
      ]);
      setTickets(ticketsRes);
      setBoardTickets(boardRes);
      setIntegrations(integrationsRes);
      setLastUpdated(new Date());
    } catch (err) {
      console.error("Failed to fetch dashboard data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  // Re-render "time ago" every 10s
  const [, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((x) => x + 1), 10000);
    return () => clearInterval(t);
  }, []);

  const stats = useMemo(() => {
    const byStatus: Record<TicketSummary["status"], number> = {
      open: 0, in_progress: 0, delivered: 0, resolved: 0, closed: 0,
    };
    const byPriority: Record<string, number> = {};
    let activeCount = 0;

    for (const t of tickets) {
      byStatus[t.status] = (byStatus[t.status] ?? 0) + 1;
      const isActive = t.status !== "closed" && t.status !== "resolved";
      if (isActive) {
        activeCount++;
        const p = (t.priority || "medium").toLowerCase();
        byPriority[p] = (byPriority[p] ?? 0) + 1;
      }
    }

    const inAttention = byStatus.open + byStatus.in_progress + byStatus.delivered;
    const pendingSync = byStatus.resolved;
    const closed = byStatus.closed;

    // Board breakdown
    const boardBySource: Record<string, { total: number; pending: number; ingested: number }> = {};
    for (const bt of boardTickets) {
      const src = bt.source_system || "unknown";
      if (!boardBySource[src]) boardBySource[src] = { total: 0, pending: 0, ingested: 0 };
      boardBySource[src].total++;
      if (bt.already_ingested) boardBySource[src].ingested++;
      else boardBySource[src].pending++;
    }
    const boardPending = boardTickets.filter((b) => !b.already_ingested).length;

    // Recent (last 24h / 7d)
    const now = Date.now();
    const day = 24 * 60 * 60 * 1000;
    const last24h = tickets.filter((t) => now - new Date(t.created_at).getTime() < day).length;
    const last7d = tickets.filter((t) => now - new Date(t.created_at).getTime() < 7 * day).length;

    const recentTickets = [...tickets]
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 6);

    return {
      byStatus,
      byPriority,
      activeCount,
      inAttention,
      pendingSync,
      closed,
      total: tickets.length,
      boardBySource,
      boardPending,
      boardTotal: boardTickets.length,
      last24h,
      last7d,
      recentTickets,
    };
  }, [tickets, boardTickets]);

  const sourceIntegrations = integrations.filter((i) => i.system_type === "source" && i.is_active);

  const donutSegments = [
    { value: stats.byStatus.open, color: "#3B82F6", label: "Abierto" },
    { value: stats.byStatus.in_progress, color: "#10B981", label: "En progreso" },
    { value: stats.byStatus.delivered, color: "#6366F1", label: "Entregado" },
    { value: stats.byStatus.resolved, color: "#F59E0B", label: "Resuelto" },
    { value: stats.byStatus.closed, color: "#94A3B8", label: "Cerrado" },
  ];

  const maxBoardCount = Math.max(1, ...Object.values(stats.boardBySource).map((v) => v.total));

  return (
    <div className="bg-[#F8FAFC] dark:bg-slate-900 text-slate-900 dark:text-slate-100 h-screen flex flex-col overflow-hidden">
      <Header
        activePage="dashboard"
        subheader={
          <>
            <div className="flex items-center gap-3">
              <span className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest">
                Estado operativo
              </span>
              <span className="text-xs text-slate-600 dark:text-slate-300">
                {stats.total} ticket{stats.total === 1 ? "" : "s"} ingestado{stats.total === 1 ? "" : "s"} · {stats.boardTotal} en board
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-500 dark:text-slate-400">
                Actualizado {timeAgo(lastUpdated.toISOString())}
              </span>
              <button
                onClick={fetchAll}
                disabled={loading}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors disabled:opacity-50"
              >
                <span className={loading ? "animate-spin" : ""}>
                  <IconRefresh />
                </span>
                Refrescar
              </button>
            </div>
          </>
        }
      />

      <main className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
          {/* KPIs */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCard
              label="En atencion"
              value={stats.inAttention}
              sub={`${stats.byStatus.open} abiertos · ${stats.byStatus.in_progress} en progreso`}
              accent="bg-emerald-500"
              icon={<IconAttention />}
              href="/"
            />
            <KpiCard
              label="Pendiente sincronizar"
              value={stats.pendingSync}
              sub="Resueltos sin cerrar en origen"
              accent="bg-amber-500"
              icon={<IconCheckCircle />}
              href="/"
            />
            <KpiCard
              label="Cerrados"
              value={stats.closed}
              sub={`${stats.last7d} nuevos en 7d`}
              accent="bg-slate-500"
              icon={<IconArchive />}
            />
            <KpiCard
              label="Board pendiente"
              value={stats.boardPending}
              sub={`${stats.boardTotal} totales · ${stats.boardTotal - stats.boardPending} ingestados`}
              accent="bg-blue-500"
              icon={<IconInbox />}
              href="/"
            />
          </div>

          {/* Row 1: status donut + priority bars */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className={`${cardCls} p-6`}>
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
                    Distribucion por estado
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Tickets locales anonimizados
                  </p>
                </div>
              </div>

              {stats.total === 0 ? (
                <EmptyState msg="Aun no hay tickets ingestados" />
              ) : (
                <div className="flex items-center gap-8">
                  <div className="shrink-0">
                    <Donut
                      segments={donutSegments}
                      centerLabel={String(stats.total)}
                      centerSub="Tickets"
                    />
                  </div>
                  <div className="flex-1 space-y-2.5 min-w-0">
                    {(Object.keys(STATUS_META) as TicketSummary["status"][]).map((s) => {
                      const meta = STATUS_META[s];
                      const count = stats.byStatus[s] || 0;
                      return (
                        <BarRow
                          key={s}
                          label={meta.label}
                          count={count}
                          total={stats.total}
                          barClass={meta.bar}
                          labelClass={meta.color}
                        />
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            <div className={`${cardCls} p-6`}>
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
                    Prioridad en atencion
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Solo tickets activos (abierto · en progreso · entregado)
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 tabular-nums">
                    {stats.activeCount}
                  </div>
                  <div className="text-xs text-slate-500 dark:text-slate-400 font-medium">activos</div>
                </div>
              </div>

              {stats.activeCount === 0 ? (
                <EmptyState msg="No hay tickets activos" />
              ) : (
                <div className="space-y-2.5">
                  {(["critical", "very high", "high", "medium", "low", "very low"] as const).map((p) => {
                    const meta = PRIORITY_META[p];
                    const count = stats.byPriority[p] || 0;
                    if (count === 0 && (p === "very high" || p === "very low")) return null;
                    return (
                      <BarRow
                        key={p}
                        label={meta.label}
                        count={count}
                        total={stats.activeCount}
                        barClass={meta.bar}
                        labelClass={meta.text}
                      />
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Row 2: board by source + recent tickets */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className={`${cardCls} p-6`}>
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
                    Board por sistema origen
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Tickets live, pendientes vs ya ingestados
                  </p>
                </div>
                <span className="px-2 py-0.5 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs font-bold rounded border border-blue-200 dark:border-blue-800">
                  {sourceIntegrations.length} origen{sourceIntegrations.length === 1 ? "" : "es"}
                </span>
              </div>

              {Object.keys(stats.boardBySource).length === 0 ? (
                <EmptyState msg="Sin tickets en el board" />
              ) : (
                <div className="space-y-4">
                  {Object.entries(stats.boardBySource)
                    .sort((a, b) => b[1].total - a[1].total)
                    .map(([src, v]) => {
                      const pendingPct = v.total > 0 ? (v.pending / maxBoardCount) * 100 : 0;
                      const ingestedPct = v.total > 0 ? (v.ingested / maxBoardCount) * 100 : 0;
                      return (
                        <div key={src}>
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-200">
                              {src}
                            </span>
                            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 tabular-nums">
                              <span className="text-blue-600 dark:text-blue-400">{v.pending} pend.</span>
                              {" · "}
                              <span className="text-emerald-600 dark:text-emerald-400">{v.ingested} ingestados</span>
                              {" · "}
                              <span className="text-slate-900 dark:text-slate-100">{v.total} total</span>
                            </span>
                          </div>
                          <div className="h-3 bg-slate-100 dark:bg-slate-700/60 rounded-full overflow-hidden flex">
                            <div
                              className="h-full bg-blue-500 transition-all duration-500"
                              style={{ width: `${pendingPct}%` }}
                              title={`${v.pending} pendientes`}
                            />
                            <div
                              className="h-full bg-emerald-500 transition-all duration-500"
                              style={{ width: `${ingestedPct}%` }}
                              title={`${v.ingested} ingestados`}
                            />
                          </div>
                        </div>
                      );
                    })}
                </div>
              )}
            </div>

            <div className={`${cardCls} p-6`}>
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
                    Ultimos ingestados
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    {stats.last24h} en 24h · {stats.last7d} en 7 dias
                  </p>
                </div>
              </div>

              {stats.recentTickets.length === 0 ? (
                <EmptyState msg="Aun no hay tickets ingestados" />
              ) : (
                <ul className="space-y-2">
                  {stats.recentTickets.map((t) => {
                    const meta = STATUS_META[t.status];
                    return (
                      <li key={t.id}>
                        <Link
                          href={`/?ticket=${t.id}`}
                          className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors group"
                        >
                          <span className={`w-2 h-2 rounded-full ${meta.bar} shrink-0 ring-4 ${meta.ring}`} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-bold text-slate-900 dark:text-slate-100 tabular-nums">
                                #{t.id}
                              </span>
                              <span className="text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                                {t.source_system}
                              </span>
                              <span className="text-xs font-mono text-slate-400 dark:text-slate-500">
                                {t.source_ticket_id}
                              </span>
                            </div>
                            <div className="text-sm text-slate-700 dark:text-slate-200 truncate mt-0.5">
                              {t.summary || "(sin asunto)"}
                            </div>
                          </div>
                          <div className="flex flex-col items-end gap-1 shrink-0">
                            <span className={`text-[10px] font-bold uppercase tracking-wider ${meta.color}`}>
                              {meta.label}
                            </span>
                            <span className="text-[10px] text-slate-400 dark:text-slate-500">
                              {timeAgo(t.created_at)}
                            </span>
                          </div>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>

          {/* Row 3: source integrations health */}
          {sourceIntegrations.length > 0 && (
            <div className={`${cardCls} p-6`}>
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
                    Integraciones origen
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Estado de las conexiones configuradas
                  </p>
                </div>
                <Link
                  href="/config"
                  className="text-xs font-semibold text-primary hover:underline"
                >
                  Configurar →
                </Link>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {sourceIntegrations.map((i) => {
                  const status = i.last_connection_status;
                  const dotColor =
                    status === "connected"
                      ? "bg-green-500"
                      : status === "error"
                      ? "bg-red-500"
                      : "bg-amber-500";
                  return (
                    <div
                      key={i.id}
                      className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-700/40 border border-slate-200 dark:border-slate-700"
                    >
                      <span className={`w-2 h-2 rounded-full ${dotColor} shrink-0 animate-pulse`} />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-bold text-slate-900 dark:text-slate-100 truncate">
                          {i.display_name}
                        </div>
                        <div className="text-xs text-slate-500 dark:text-slate-400 truncate">
                          {i.project_key || i.system_name} · {i.connector_type}
                        </div>
                      </div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 shrink-0">
                        {status || "sin datos"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {loading && tickets.length === 0 && (
            <div className="text-center py-12 text-sm text-slate-500 dark:text-slate-400">
              Cargando metricas…
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function EmptyState({ msg }: { msg: string }) {
  return (
    <div className="text-center py-8 text-sm text-slate-400 dark:text-slate-500 italic">
      {msg}
    </div>
  );
}
