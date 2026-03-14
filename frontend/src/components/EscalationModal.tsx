"use client";

import { useState, useRef } from "react";

interface Props {
  ticketId: string;
  open: boolean;
  onClose: () => void;
  onConfirm: (data: EscalationData) => void;
}

export interface EscalationData {
  level: string;
  reason: string;
  notes: string;
  attachments: File[];
}

const IconShield = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
  </svg>
);
const IconClose = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
);
const IconUpload = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-slate-400">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
  </svg>
);
const IconArrowUp = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/>
  </svg>
);
const IconWarning = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
  </svg>
);
const IconFile = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
  </svg>
);

const escalationLevels = [
  { value: "", label: "Seleccionar nivel..." },
  { value: "l2", label: "Nivel 2 — Soporte Tecnico" },
  { value: "l3", label: "Nivel 3 — Infraestructura" },
  { value: "security", label: "Seguridad" },
];

const escalationReasons = [
  { value: "", label: "Seleccionar motivo..." },
  { value: "complex_error", label: "Error complejo no resuelto" },
  { value: "no_permission", label: "Falta de permisos" },
  { value: "physical_restart", label: "Requiere reinicio fisico" },
  { value: "other", label: "Otro" },
];

export function EscalationModal({ ticketId, open, onClose, onConfirm }: Props) {
  const [level, setLevel] = useState("");
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");
  const [attachments, setAttachments] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!open) return null;

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    setAttachments((prev) => [...prev, ...files]);
  };

  const removeFile = (idx: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSubmit = () => {
    if (!level || !reason) return;
    onConfirm({ level, reason, notes, attachments });
    setLevel("");
    setReason("");
    setNotes("");
    setAttachments([]);
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm" />

      <div className="relative w-full max-w-lg bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <div className="flex items-center gap-3">
            <h2 className="text-base font-bold text-slate-900">Escalar Incidencia</h2>
            <span className="px-2 py-0.5 bg-primary/10 text-primary text-xs font-bold rounded">[ANON] {ticketId}</span>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors">
            <IconClose />
          </button>
        </div>

        {/* Warning */}
        <div className="mx-6 mt-4 px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-3">
          <span className="text-amber-500 mt-0.5"><IconWarning /></span>
          <p className="text-xs text-amber-800 leading-relaxed">
            La informacion compartida con el nivel superior estara <strong>anonimizada</strong>. Los datos personales no seran visibles en la escalacion.
          </p>
        </div>

        {/* Form */}
        <div className="px-6 py-4 space-y-4">
          {/* Level */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">Nivel de escalado</label>
            <select value={level} onChange={(e) => setLevel(e.target.value)}
              className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all">
              {escalationLevels.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
            </select>
          </div>

          {/* Reason */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">Motivo de escalacion</label>
            <select value={reason} onChange={(e) => setReason(e.target.value)}
              className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all">
              {escalationReasons.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">Notas adicionales</label>
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} placeholder="Describe detalles relevantes para la escalacion..."
              className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all resize-none placeholder:text-slate-400" />
          </div>

          {/* Attachments */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">Adjuntos</label>
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-lg p-5 text-center cursor-pointer transition-colors ${dragOver ? "border-primary bg-primary/5" : "border-slate-200 hover:border-slate-300"}`}
            >
              <IconUpload />
              <p className="text-xs text-slate-500 mt-2">Arrastra archivos o <span className="text-primary font-semibold">haz click para seleccionar</span></p>
              <p className="text-[10px] text-slate-400 mt-1 flex items-center justify-center gap-1">
                <IconShield /> Las capturas se anonimizan automaticamente
              </p>
            </div>
            <input ref={fileInputRef} type="file" multiple className="hidden" onChange={(e) => {
              if (e.target.files) setAttachments((prev) => [...prev, ...Array.from(e.target.files!)]);
            }} />

            {attachments.length > 0 && (
              <div className="mt-2 space-y-1">
                {attachments.map((f, i) => (
                  <div key={i} className="flex items-center justify-between px-3 py-1.5 bg-slate-50 rounded-lg border border-slate-200">
                    <div className="flex items-center gap-2 text-xs text-slate-600">
                      <IconFile />
                      <span className="truncate max-w-[250px]">{f.name}</span>
                      <span className="text-slate-400">({(f.size / 1024).toFixed(0)} KB)</span>
                    </div>
                    <button onClick={() => removeFile(i)} className="text-slate-400 hover:text-red-500 transition-colors">
                      <IconClose />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-200 bg-slate-50">
          <button onClick={onClose}
            className="px-4 py-2 text-sm font-semibold text-slate-600 border border-slate-200 rounded-lg hover:bg-white transition-colors">
            Cancelar
          </button>
          <button onClick={handleSubmit} disabled={!level || !reason}
            className="flex items-center gap-2 px-5 py-2 bg-primary text-white text-sm font-bold rounded-lg hover:bg-blue-600 transition-colors shadow-lg shadow-primary/20 disabled:bg-slate-300 disabled:shadow-none disabled:cursor-not-allowed">
            <IconArrowUp />
            Confirmar escalacion
          </button>
        </div>
      </div>
    </div>
  );
}
