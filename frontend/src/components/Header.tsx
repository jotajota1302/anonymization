"use client";

import Link from "next/link";
import { useAuthStore } from "@/stores/authStore";
import { useAppStore } from "@/stores/appStore";

interface HeaderProps {
  activePage: "incidencias" | "dashboard" | "config";
  isConnected?: boolean;
  subheader?: React.ReactNode;
}

function getInitials(name?: string): string {
  if (!name) return "OP";
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

export function Header({ activePage, isConnected: isConnectedProp, subheader }: HeaderProps) {
  const { user, skipAuth, isAuthenticated, logout } = useAuthStore();
  const wsConnected = useAppStore((s) => s.isConnected);
  // Use prop if provided, otherwise read from global store
  const isConnected = isConnectedProp ?? wsConnected;

  const displayName = (!skipAuth && isAuthenticated && user)
    ? (user.displayName || user.name || "Operador")
    : "Operador NTT";
  const displayEmail = (!skipAuth && isAuthenticated && user)
    ? (user.email || user.preferred_username || "")
    : "operador@nttdata.com";
  const initials = (!skipAuth && isAuthenticated && user)
    ? getInitials(user.displayName || user.name)
    : "OP";

  const navItems = [
    { id: "incidencias", label: "Incidencias", href: "/" },
    { id: "dashboard", label: "Dashboard", href: "/dashboard" },
    { id: "config", label: "Configuracion", href: "/config" },
  ] as const;

  return (
    <>
      {/* Glass Header */}
      <header className="sticky top-0 z-50 glass-header border-b border-slate-200 dark:border-slate-700 px-6 h-16 flex items-center justify-between bg-white/80 dark:bg-slate-900/80 backdrop-blur">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="h-8 px-2 bg-white dark:bg-slate-800 rounded flex items-center border border-slate-200 dark:border-slate-700">
              <img src="/logo-ntt.jpg" alt="NTT DATA" width={80} height={20} className="h-5 object-contain" />
            </div>
            <h1 className="text-slate-800 dark:text-slate-100 font-bold text-lg tracking-tight">Plataforma de Anonimizacion</h1>
          </div>
          <div className="h-6 w-px bg-slate-200 dark:bg-slate-700 mx-2" />
          <nav className="flex items-center gap-1">
            {navItems.map((item) =>
              item.id === activePage ? (
                <span key={item.id} className="px-3 py-1.5 text-xs font-semibold text-primary bg-primary/10 rounded-lg">
                  {item.label}
                </span>
              ) : (
                <Link key={item.id} href={item.href} className="px-3 py-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors">
                  {item.label}
                </Link>
              )
            )}
          </nav>
          {/* Connection status moved to user area on the right */}
        </div>
        <div className="flex items-center gap-3">
          {<div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border ${
              isConnected
                ? "bg-green-50 dark:bg-green-900/30 border-green-100 dark:border-green-800"
                : "bg-red-50 dark:bg-red-900/30 border-red-100 dark:border-red-800"
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${isConnected ? "bg-green-500 animate-pulse" : "bg-red-500"}`} />
              <span className={`text-[10px] font-bold uppercase tracking-wider ${isConnected ? "text-green-700 dark:text-green-400" : "text-red-700 dark:text-red-400"}`}>
                {isConnected ? "Online" : "Offline"}
              </span>
            </div>}
          <div className="h-6 w-px bg-slate-200 dark:bg-slate-700" />
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-xs font-bold text-slate-900 dark:text-slate-100 leading-tight">{displayName}</p>
              {displayEmail && <p className="text-xs text-slate-500 dark:text-slate-400 leading-tight">{displayEmail}</p>}
            </div>
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-blue-700 flex items-center justify-center text-sm font-bold text-white border-2 border-white dark:border-slate-800 shadow-sm">
              {initials}
            </div>
            {!skipAuth && isAuthenticated && (
              <button
                onClick={logout}
                aria-label="Cerrar sesion"
                title="Cerrar sesion"
                className="p-1.5 text-slate-400 dark:text-slate-500 hover:text-red-500 dark:hover:text-red-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Sub-header */}
      {subheader && (
        <div className="bg-slate-100 dark:bg-slate-950 text-slate-700 dark:text-white px-6 py-2.5 flex items-center justify-between border-b border-slate-200 dark:border-slate-800">
          {subheader}
        </div>
      )}
    </>
  );
}
