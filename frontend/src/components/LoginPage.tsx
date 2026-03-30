"use client";

import { useEffect, useRef } from "react";
import { useAuthStore } from "@/stores/authStore";

const IconShield = () => (
  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-primary">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    <polyline points="9 12 12 15 15 10" />
  </svg>
);

const IconSpinner = ({ className = "" }: { className?: string }) => (
  <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
  </svg>
);

export function LoginPage() {
  const { deviceCode, isPolling, loginError, user, isAuthenticated, startLogin, pollForToken, cancelLogin } = useAuthStore();
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Start polling when device code is active
  useEffect(() => {
    if (!isPolling || !deviceCode) {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      return;
    }

    pollIntervalRef.current = setInterval(async () => {
      const result = await pollForToken();
      if (result !== "pending") {
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      }
    }, 5000);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [isPolling, deviceCode, pollForToken]);

  // Brief success state
  if (isAuthenticated && user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900">
        <div className="text-center animate-in fade-in duration-300">
          <div className="w-16 h-16 mx-auto mb-4 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-green-600 dark:text-green-400">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
          <p className="text-lg font-bold text-slate-900 dark:text-slate-100">Bienvenido, {user.displayName || user.name || user.email || "Operador"}</p>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Cargando plataforma...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-blue-50/30 to-slate-100 dark:from-slate-900 dark:via-slate-900 dark:to-slate-800">
      <div className="w-full max-w-md mx-4">
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-700 p-8">
          {/* Logo & Title */}
          <div className="text-center mb-8">
            <div className="flex items-center justify-center gap-3 mb-4">
              <div className="h-10 px-3 bg-white dark:bg-slate-700 rounded-lg flex items-center border border-slate-200 dark:border-slate-600">
                <img src="/logo-ntt.jpg" alt="NTT DATA" width={100} height={25} className="h-6 object-contain" />
              </div>
            </div>
            <div className="w-16 h-16 mx-auto mb-4 bg-primary/10 rounded-2xl flex items-center justify-center border border-primary/20">
              <IconShield />
            </div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">Plataforma de Anonimizacion</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">Sistema de intermediacion GDPR para soporte offshore</p>
          </div>

          {/* Login States */}
          {!deviceCode && !isPolling && (
            <div className="space-y-4">
              <button
                onClick={startLogin}
                className="w-full py-3 px-4 bg-primary text-white rounded-xl text-sm font-bold hover:bg-blue-600 active:scale-[0.98] transition-all shadow-lg shadow-primary/20 flex items-center justify-center gap-2"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" /><polyline points="10 17 15 12 10 7" /><line x1="15" y1="12" x2="3" y2="12" />
                </svg>
                Iniciar sesion con OKTA
              </button>
              <p className="text-xs text-center text-slate-400 dark:text-slate-500">
                Usa tu cuenta corporativa NTT DATA
              </p>
            </div>
          )}

          {deviceCode && isPolling && (
            <div className="space-y-5">
              <div className="text-center">
                <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2 uppercase tracking-wider">Codigo de verificacion</p>
                <p className="text-3xl font-mono font-bold text-primary tracking-widest select-all">{deviceCode.user_code}</p>
              </div>

              <a
                href={deviceCode.verification_uri_complete}
                target="_blank"
                rel="noopener noreferrer"
                className="block w-full py-3 px-4 bg-purple-600 text-white rounded-xl text-sm font-bold hover:bg-purple-700 transition-colors text-center"
              >
                Abrir pagina de login OKTA
              </a>

              <div className="flex items-center justify-center gap-3 py-3">
                <IconSpinner className="w-5 h-5 text-primary" />
                <span className="text-sm text-slate-500 dark:text-slate-400">Esperando autenticacion en el navegador...</span>
              </div>

              <button
                onClick={cancelLogin}
                className="w-full py-2 text-sm text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
              >
                Cancelar
              </button>
            </div>
          )}

          {/* Error */}
          {loginError && (
            <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <p className="text-xs text-red-700 dark:text-red-400 font-medium">{loginError}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-slate-400 dark:text-slate-500 mt-6">
          NTT DATA EMEAL &mdash; Plataforma GDPR-Compliant
        </p>
      </div>
    </div>
  );
}
