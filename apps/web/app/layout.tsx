import type { Metadata } from "next";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "APOLO — Prover",
  description: "Assistente conversacional da Prover Tecnologia",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
