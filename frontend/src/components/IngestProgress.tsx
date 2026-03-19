"use client";

import { useEffect, useRef } from "react";
import { useAppStore } from "@/stores/appStore";
import { IngestStep, DetectorResult } from "@/types";

const STEPS = [
  { key: "reading_source", label: "Leyendo info en origen" },
  { key: "detecting_pii", label: "Revisando datos sensibles" },
  { key: "creating_destination", label: "Generando copia anonimizada en destino" },
  { key: "completed", label: "Completado" },
] as const;

const DETECTOR_LABELS: Record<string, string> = {
  regex: "Regex",
  presidio: "Presidio NLP",
  agente: "Agente IA",
  anonymize: "Anonimizar",
};

const Spinner = ({ className = "" }: { className?: string }) => (
  <svg className={`animate-spin w-4 h-4 ${className}`} viewBox="0 0 24 24" fill="none">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
  </svg>
);

const CheckIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const ErrorIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const ShieldIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
  </svg>
);

function DetectorBadge({ name, result }: { name: string; result: DetectorResult }) {
  const label = DETECTOR_LABELS[name] || name;

  if (result.status === "pending") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-500 border border-slate-200 dark:border-slate-700">
        <span className="w-1.5 h-1.5 rounded-full bg-slate-300 dark:bg-slate-600" />
        {label}
      </span>
    );
  }

  if (result.status === "skipped") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium bg-slate-50 dark:bg-slate-800/50 text-slate-400 dark:text-slate-600 border border-slate-200 dark:border-slate-700 border-dashed">
        {label}
        <span className="text-[10px] italic">n/a</span>
      </span>
    );
  }

  if (result.status === "in_progress") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800">
        <Spinner className="w-3 h-3" />
        {label}
      </span>
    );
  }

  // completed
  const count = result.count ?? 0;
  const found = count > 0;

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-bold border ${
      found
        ? "bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 border-amber-300 dark:border-amber-700"
        : "bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-300 dark:border-emerald-700"
    }`}>
      {found ? (
        <ShieldIcon />
      ) : (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      )}
      {label}
      {found && <span className="ml-0.5 px-1 py-px rounded bg-amber-200 dark:bg-amber-800 text-amber-800 dark:text-amber-200 text-[10px] font-bold">{count}</span>}
    </span>
  );
}

function StepIndicator({ status, index }: { status: "pending" | "in_progress" | "completed" | "error"; index: number }) {
  if (status === "completed") {
    return (
      <div className="w-7 h-7 rounded-full bg-emerald-500 flex items-center justify-center text-white shrink-0 shadow-sm shadow-emerald-500/30">
        <CheckIcon />
      </div>
    );
  }
  if (status === "error") {
    return (
      <div className="w-7 h-7 rounded-full bg-red-500 flex items-center justify-center text-white shrink-0 shadow-sm shadow-red-500/30">
        <ErrorIcon />
      </div>
    );
  }
  if (status === "in_progress") {
    return (
      <div className="w-7 h-7 rounded-full bg-blue-500 flex items-center justify-center text-white shrink-0 shadow-sm shadow-blue-500/30">
        <Spinner className="w-4 h-4 text-white" />
      </div>
    );
  }
  // pending
  return (
    <div className="w-7 h-7 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-slate-400 dark:text-slate-500 shrink-0 text-xs font-bold">
      {index + 1}
    </div>
  );
}

export function IngestProgress() {
  const ingestProgress = useAppStore((s) => s.ingestProgress);

  // Accumulate per-step data across WS messages so completed steps keep their info
  const stepDataRef = useRef<Record<string, { detail?: string; detectors?: Record<string, DetectorResult> }>>({});

  useEffect(() => {
    if (!ingestProgress) {
      stepDataRef.current = {};
      return;
    }
    const key = ingestProgress.step;
    const prev = stepDataRef.current[key] || {};
    stepDataRef.current[key] = {
      detail: ingestProgress.detail ?? prev.detail,
      detectors: ingestProgress.detectors ?? prev.detectors,
    };
  }, [ingestProgress]);

  // Determine each step's visual status based on current progress
  const getStepStatus = (stepIndex: number): "pending" | "in_progress" | "completed" | "error" => {
    if (!ingestProgress) return stepIndex === 0 ? "in_progress" : "pending";

    const currentIndex = ingestProgress.step_index;

    if (stepIndex < currentIndex) return "completed";
    if (stepIndex === currentIndex) {
      if (ingestProgress.status === "error") return "error";
      if (ingestProgress.status === "completed") return "completed";
      return "in_progress";
    }
    return "pending";
  };

  const stepData = stepDataRef.current;

  return (
    <div className="w-full max-w-md" role="status" aria-label="Progreso de ingesta">
      <div className="space-y-0">
        {STEPS.map((step, idx) => {
          const status = getStepStatus(idx);
          const isLast = idx === STEPS.length - 1;
          const data = stepData[step.key];
          const showDetectors = step.key === "detecting_pii" && data?.detectors;

          return (
            <div key={step.key} className="flex gap-3">
              {/* Vertical line + indicator */}
              <div className="flex flex-col items-center">
                <StepIndicator status={status} index={idx} />
                {!isLast && (
                  <div className={`w-0.5 flex-1 min-h-[24px] transition-colors duration-300 ${
                    status === "completed" ? "bg-emerald-400 dark:bg-emerald-500" : "bg-slate-200 dark:bg-slate-700"
                  }`} />
                )}
              </div>

              {/* Label + detector badges */}
              <div className={`pb-5 pt-1 ${isLast ? "pb-0" : ""}`}>
                <span className={`text-sm font-medium transition-colors ${
                  status === "completed" ? "text-emerald-700 dark:text-emerald-400" :
                  status === "in_progress" ? "text-slate-900 dark:text-slate-100" :
                  status === "error" ? "text-red-600 dark:text-red-400" :
                  "text-slate-400 dark:text-slate-500"
                }`}>
                  {step.label}
                </span>

                {status === "error" && data?.detail && (
                  <p className="text-xs text-red-500 dark:text-red-400 mt-1">{data.detail}</p>
                )}

                {status === "completed" && data?.detail && (
                  <p className="text-xs text-emerald-600 dark:text-emerald-400/80 mt-0.5 font-mono">{data.detail}</p>
                )}

                {showDetectors && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {Object.entries(data!.detectors!).map(([dk, det]) => (
                      <DetectorBadge key={dk} name={dk} result={det} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
