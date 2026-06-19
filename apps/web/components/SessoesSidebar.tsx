"use client";

import { useEffect, useState } from "react";
import { Plus, Mic } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Sessao = {
  id: string;
  titulo: string | null;
  canal: "texto" | "voz";
  msg_count: number;
  updated_at: string;
};

export function SessoesSidebar({
  sessaoAtiva,
  onSelecionar,
}: {
  sessaoAtiva: string | null;
  onSelecionar: (id: string | null) => void;
}) {
  const [sessoes, setSessoes] = useState<Sessao[]>([]);

  useEffect(() => {
    api<Sessao[]>("/api/sessoes").then(setSessoes).catch(() => setSessoes([]));
  }, [sessaoAtiva]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 p-3">
      <button
        onClick={() => onSelecionar(null)}
        className="inline-flex items-center justify-center gap-2 rounded-full bg-ap-blue px-4 py-2.5 text-sm font-semibold text-white shadow-[0_0_24px_rgba(31,143,227,0.3)] transition-colors hover:bg-ap-blue-hover"
      >
        <Plus size={15} /> Nova conversa
      </button>

      <div className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto">
        {sessoes.length === 0 && (
          <p className="px-3 py-4 text-center text-xs text-ap-text-faint">
            nenhuma conversa ainda
          </p>
        )}
        {sessoes.map((s) => (
          <button
            key={s.id}
            onClick={() => onSelecionar(s.id)}
            className={cn(
              "rounded-lg border border-transparent px-3.5 py-3 text-left transition-all hover:bg-white/5",
              sessaoAtiva === s.id && "border-ap-blue/30 bg-ap-blue-soft"
            )}
          >
            <div className="flex items-center gap-2">
              {sessaoAtiva === s.id && (
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-ap-blue shadow-[0_0_8px_#1F8FE3]" />
              )}
              {s.canal === "voz" && <Mic size={11} className="shrink-0 text-ap-blue" />}
              <span className="truncate text-[13px] font-semibold text-ap-text">
                {s.titulo || "Conversa sem título"}
              </span>
            </div>
            <span className="mt-1 block font-mono text-[11px] text-ap-text-faint">
              {s.msg_count} mensagens
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
