"use client";

import { useEffect, useRef } from "react";
import { useAuthStore } from "@/stores/authStore";
import { LoginPage } from "./LoginPage";

const AUTH_STATUS_POLL_MS = 60_000;

function LoadingScreen() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900">
      <div className="text-center">
        <div className="flex items-center justify-center gap-3 mb-6">
          <div className="h-10 px-3 bg-white dark:bg-slate-800 rounded-lg flex items-center border border-slate-200 dark:border-slate-700">
            <img src="/logo-ntt.jpg" alt="NTT DATA" width={100} height={25} className="h-6 object-contain" />
          </div>
        </div>
        <svg className="animate-spin w-8 h-8 text-primary mx-auto mb-4" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        <p className="text-sm text-slate-500 dark:text-slate-400">Verificando sesion...</p>
      </div>
    </div>
  );
}

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, skipAuth, checkStatus } = useAuthStore();
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Check auth status on mount
  useEffect(() => {
    if (!skipAuth) {
      checkStatus();
    }
  }, [skipAuth, checkStatus]);

  // Periodic status check to detect token expiry
  useEffect(() => {
    if (skipAuth || !isAuthenticated) return;

    pollRef.current = setInterval(() => {
      checkStatus();
    }, AUTH_STATUS_POLL_MS);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [skipAuth, isAuthenticated, checkStatus]);

  if (skipAuth) return <>{children}</>;
  if (isLoading) return <LoadingScreen />;
  if (!isAuthenticated) return <LoginPage />;
  return <>{children}</>;
}
