"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Database, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { ChartRenderer } from "./ChartRenderer";

export type EtapaKey = "entendendo" | "gerando" | "consultando" | "respondendo";
export type EtapaState = "pending" | "active" | "done";
export type Etapa = { key: EtapaKey; label: string; state: EtapaState };

export const ETAPAS_INICIAIS: Etapa[] = [
  { key: "entendendo", label: "Entendendo a pergunta", state: "active" },
  { key: "gerando", label: "Gerando a consulta SQL", state: "pending" },
  { key: "consultando", label: "Consultando a base", state: "pending" },
  { key: "respondendo", label: "Preparando a resposta", state: "pending" },
];

export type Mensagem = {
  id?: string;
  papel: "user" | "apolo";
  texto: string;
  status?: string | null;
  etapas?: Etapa[] | null;
  dominio?: string | null;
  confidence?: number | null;
  sql?: string | null;
  grafico_sugerido?: string | null;
  spec_grafico?: any;
  origem?: "texto" | "voz";
  loading?: boolean;
};

function horaAgora() {
  return new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

export function ChatMessage({ msg }: { msg: Mensagem }) {
  if (msg.papel === "user") {
    return (
      <div className="flex flex-col items-end gap-1.5">
        <div className="max-w-[72%] rounded-[22px_22px_4px_22px] bg-ap-blue px-5 py-3 text-sm font-medium leading-relaxed text-white shadow-[0_0_24px_rgba(31,143,227,0.25)]">
          {msg.texto}
        </div>
        <div className="flex items-center gap-1.5 font-mono text-[11px] text-ap-text-faint">
          <span>{horaAgora()}</span>
          <span>·</span>
          <span>você</span>
          <span>·</span>
          <span>via {msg.origem === "voz" ? "voz" : "texto"}</span>
        </div>
      </div>
    );
  }

  const mostrarEtapas = msg.loading && !msg.texto && msg.etapas && msg.etapas.length > 0;

  return (
    <div className="flex items-start gap-4">
      <div
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-ap-blue/40 bg-ap-blue/15 text-ap-blue shadow-[0_0_16px_rgba(31,143,227,0.25)]",
          msg.loading && "animate-pulse"
        )}
      >
        <Database size={16} />
      </div>

      <div className="min-w-0 max-w-[760px] flex-1">
        {msg.dominio && (
          <div className="mb-2 inline-flex items-center gap-1.5 rounded-md border border-ap-blue/30 bg-ap-blue-soft px-2 py-1 font-mono text-[10px] font-semibold uppercase tracking-widest text-ap-blue">
            {msg.dominio}
            {msg.confidence != null && (
              <span className="text-ap-text-faint">· conf {Math.round((msg.confidence || 0) * 100)}%</span>
            )}
          </div>
        )}

        {mostrarEtapas && (
          <div className="flex flex-col gap-2 py-1">
            {msg.etapas!.map((e) => (
              <div
                key={e.key}
                className={cn(
                  "flex items-center gap-2.5 font-mono text-[13px] transition-colors",
                  e.state === "done"
                    ? "text-ap-success"
                    : e.state === "active"
                    ? "text-ap-blue"
                    : "text-ap-text-faint"
                )}
              >
                {e.state === "done" ? (
                  <Check size={13} />
                ) : (
                  <span
                    className={cn(
                      "h-2 w-2 rounded-full bg-current",
                      e.state === "active" ? "animate-pulse opacity-100" : "opacity-40"
                    )}
                  />
                )}
                {e.label}
              </div>
            ))}
          </div>
        )}

        {msg.texto && (
          <div className="prose prose-invert prose-sm max-w-none prose-strong:text-ap-blue prose-headings:text-ap-text">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.texto}</ReactMarkdown>
          </div>
        )}

        {msg.grafico_sugerido && msg.spec_grafico && (
          <div className="mt-3">
            <ChartRenderer tipo={msg.grafico_sugerido} spec={msg.spec_grafico} />
          </div>
        )}

        {msg.sql && (
          <details className="group mt-3 text-xs">
            <summary className="flex cursor-pointer list-none items-center gap-1.5 font-mono text-ap-text-faint transition-colors hover:text-ap-text-muted">
              <ChevronRight size={12} className="transition-transform group-open:rotate-90" />
              ver SQL gerado
            </summary>
            <pre className="mt-2 overflow-x-auto rounded-lg border border-white/5 bg-ap-black p-3 font-mono text-[11px] leading-relaxed text-ap-text-muted">
              {msg.sql}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}
