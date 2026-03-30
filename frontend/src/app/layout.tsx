import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { DarkModeInit } from "@/components/DarkModeInit";
import { AuthGate } from "@/components/AuthGate";
import { WebSocketProvider } from "@/components/WebSocketProvider";

const inter = Inter({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Plataforma Anonimizacion Ticketing | NTT DATA",
  description: "Plataforma de gestion de tickets con anonimizacion GDPR",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" suppressHydrationWarning>
      <body className={`${inter.className} h-screen overflow-hidden antialiased bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100`}>
        <DarkModeInit />
        <AuthGate>
          <WebSocketProvider />
          <a
            href="#main-content"
            className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:px-4 focus:py-2 focus:bg-accent focus:text-white focus:rounded-lg"
          >
            Saltar al contenido principal
          </a>
          {children}
        </AuthGate>
      </body>
    </html>
  );
}
