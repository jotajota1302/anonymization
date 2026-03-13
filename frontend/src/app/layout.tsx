import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Plataforma Anonimizacion Ticketing",
  description: "Plataforma de gestion de tickets con anonimizacion GDPR",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className="h-screen overflow-hidden">{children}</body>
    </html>
  );
}
