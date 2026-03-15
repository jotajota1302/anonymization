"use client";

interface HeaderProps {
  activePage: "incidencias" | "config";
  isConnected?: boolean;
  subheader?: React.ReactNode;
}

export function Header({ activePage, isConnected, subheader }: HeaderProps) {
  const navItems = [
    { id: "incidencias", label: "Incidencias", href: "/" },
    { id: "config", label: "Configuracion", href: "/config" },
  ] as const;

  return (
    <>
      {/* Glass Header */}
      <header className="sticky top-0 z-50 glass-header border-b border-slate-200 dark:border-slate-700 px-6 h-16 flex items-center justify-between bg-white/80 dark:bg-slate-900/80 backdrop-blur">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="h-8 px-2 bg-white dark:bg-slate-800 rounded flex items-center border border-slate-200 dark:border-slate-700">
              <img src="/logo-ntt.jpg" alt="NTT DATA" className="h-5 object-contain" />
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
                <a key={item.id} href={item.href} className="px-3 py-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors">
                  {item.label}
                </a>
              )
            )}
          </nav>
          {isConnected !== undefined && (
            <>
              <div className="h-6 w-px bg-slate-200 dark:bg-slate-700 mx-1" />
              <div className="flex items-center gap-2 px-3 py-1 bg-green-50 dark:bg-green-900/30 rounded-full border border-green-100 dark:border-green-800">
                <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-500 animate-pulse" : "bg-red-500"}`} />
                <span className={`text-xs font-bold uppercase tracking-wider ${isConnected ? "text-green-700 dark:text-green-400" : "text-red-700 dark:text-red-400"}`}>
                  {isConnected ? "Conectado" : "Desconectado"}
                </span>
              </div>
            </>
          )}
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3 pl-2">
            <div className="text-right">
              <p className="text-xs font-bold text-slate-900 dark:text-slate-100 leading-tight">Operador NTT</p>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-tight">operador@nttdata.com</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-blue-700 flex items-center justify-center text-sm font-bold text-white border-2 border-white dark:border-slate-800 shadow-sm">
              OP
            </div>
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
