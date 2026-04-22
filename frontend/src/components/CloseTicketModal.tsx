"use client";

import { useState, useEffect, useRef } from "react";

interface CloseTicketModalProps {
  open: boolean;
  defaultSummary: string;
  isSubmitting: boolean;
  onCancel: () => void;
  onConfirm: (payload: { time_spent: string; summary: string }) => void;
}

const TIME_RE = /^\s*(\d+w\s*)?(\d+d\s*)?(\d+(\.\d+)?h\s*)?(\d+m\s*)?$/i;

export function CloseTicketModal({
  open,
  defaultSummary,
  isSubmitting,
  onCancel,
  onConfirm,
}: CloseTicketModalProps) {
  const [timeSpent, setTimeSpent] = useState("");
  const [summary, setSummary] = useState("");
  const [timeError, setTimeError] = useState<string | null>(null);
  const summaryRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (open) {
      setSummary(defaultSummary);
      setTimeSpent("");
      setTimeError(null);
      // focus summary for quick edits
      setTimeout(() => summaryRef.current?.focus(), 60);
    }
  }, [open, defaultSummary]);

  if (!open) return null;

  const validateTime = (v: string): boolean => {
    if (!v.trim()) return true; // empty is OK → IA will estimate
    if (!TIME_RE.test(v.trim())) return false;
    const hasToken = /\d/.test(v);
    return hasToken;
  };

  const handleConfirm = () => {
    if (!validateTime(timeSpent)) {
      setTimeError("Formato invalido. Usa p.ej. '2h 30m', '45m', '1h', o dejalo vacio para que lo estime la IA.");
      return;
    }
    setTimeError(null);
    if (!summary.trim()) {
      return;
    }
    onConfirm({ time_spent: timeSpent.trim(), summary: summary.trim() });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl p-6 max-w-xl w-full mx-4 border border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
              <line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>
              <line x1="3" y1="10" x2="21" y2="10"/>
              <polyline points="9 16 11 18 15 14" />
            </svg>
          </div>
          <div className="min-w-0">
            <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">Cerrar ticket</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Cierra destino y origen, publica resolucion y registra horas trabajadas.
            </p>
          </div>
        </div>

        {/* Summary */}
        <div className="mb-4">
          <label htmlFor="close-summary" className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
            Resumen de resolucion
          </label>
          <textarea
            id="close-summary"
            ref={summaryRef}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            rows={5}
            placeholder="Resumen que se publicara en el ticket origen (de-anonimizado)"
            className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-slate-100 outline-none focus:ring-2 focus:ring-primary focus:border-transparent resize-none"
          />
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
            Prerrellenado con la ultima respuesta del agente. Editalo si quieres afinarlo antes de publicar.
          </p>
        </div>

        {/* Time spent */}
        <div className="mb-5">
          <label htmlFor="close-time" className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
            Horas incurridas <span className="text-slate-400 font-normal">(opcional)</span>
          </label>
          <input
            id="close-time"
            type="text"
            value={timeSpent}
            onChange={(e) => { setTimeSpent(e.target.value); setTimeError(null); }}
            placeholder="2h 30m · 45m · 1h — dejalo vacio y lo estima la IA"
            className={`w-full px-3 py-2 bg-white dark:bg-slate-900 border rounded-lg text-sm font-mono text-slate-900 dark:text-slate-100 outline-none focus:ring-2 focus:ring-primary focus:border-transparent ${
              timeError ? "border-red-400 dark:border-red-500" : "border-slate-200 dark:border-slate-700"
            }`}
          />
          {timeError ? (
            <p className="text-xs text-red-600 dark:text-red-400 mt-1">{timeError}</p>
          ) : (
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
              Formato Jira: <span className="font-mono">w</span>eeks,
              <span className="font-mono"> d</span>ays,
              <span className="font-mono"> h</span>ours,
              <span className="font-mono"> m</span>inutes. Si lo dejas vacio la IA lo estimara del historial.
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-2 border-t border-slate-100 dark:border-slate-700">
          <button
            onClick={onCancel}
            disabled={isSubmitting}
            className="px-4 py-2 text-sm font-bold text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-700 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            onClick={handleConfirm}
            disabled={isSubmitting || !summary.trim()}
            className="flex items-center gap-2 px-5 py-2 text-sm font-bold text-white bg-primary rounded-lg hover:bg-blue-600 transition-colors shadow-lg shadow-primary/20 disabled:opacity-50"
          >
            {isSubmitting ? (
              <>
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Cerrando...
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                Confirmar y cerrar
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
