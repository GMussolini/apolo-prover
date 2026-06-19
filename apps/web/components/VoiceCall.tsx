"use client";

import { useEffect, useRef } from "react";
import { Mic, MicOff, PhoneOff, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export type VoiceTurno = { papel: "user" | "apolo"; texto: string };
type Estado = "idle" | "conectando" | "ouvindo" | "processando" | "falando" | "erro";

const ROTULO: Record<Estado, string> = {
  idle: "",
  conectando: "Conectando…",
  ouvindo: "Estou ouvindo",
  processando: "Pensando…",
  falando: "APOLO falando",
  erro: "Erro na chamada",
};

export function VoiceCall({
  estado,
  nivel,
  turnos,
  erro,
  mutado,
  onToggleMute,
  onEncerrar,
}: {
  estado: Estado;
  nivel: number;
  turnos: VoiceTurno[];
  erro: string | null;
  mutado: boolean;
  onToggleMute: () => void;
  onEncerrar: () => void;
}) {
  const fimRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    fimRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turnos]);

  const ativoOnda = estado === "ouvindo" || estado === "falando";
  // escala do orb: reage ao microfone quando ouvindo; respira quando falando
  const escala = 1 + (estado === "ouvindo" ? nivel * 0.5 : 0);

  const cor =
    estado === "erro"
      ? { de: "#FF4D5E", para: "#8E1A2A", glow: "rgba(255,77,94,.55)" }
      : estado === "processando"
      ? { de: "#FFC04D", para: "#B97D12", glow: "rgba(255,176,32,.5)" }
      : estado === "falando"
      ? { de: "#7CC4F5", para: "#1F8FE3", glow: "rgba(79,176,239,.6)" }
      : { de: "#4FB0EF", para: "#0E6BB8", glow: "rgba(31,143,227,.55)" };

  return (
    <div className="absolute inset-0 z-30 flex flex-col bg-ap-black/95 backdrop-blur-sm md:flex-row">
      {/* ━━━ lado do orb ━━━ */}
      <div className="flex flex-1 flex-col items-center justify-center gap-10 p-8">
        <div className="relative flex items-center justify-center" style={{ width: 280, height: 280 }}>
          {/* anéis de ripple */}
          {ativoOnda && (
            <>
              <span
                className="absolute rounded-full opacity-30"
                style={{
                  width: 280, height: 280, border: `1px solid ${cor.de}`,
                  animation: "vc-ripple 2.4s ease-out infinite",
                }}
              />
              <span
                className="absolute rounded-full opacity-20"
                style={{
                  width: 280, height: 280, border: `1px solid ${cor.de}`,
                  animation: "vc-ripple 2.4s ease-out infinite 1.2s",
                }}
              />
            </>
          )}
          {/* brilho */}
          <div
            className="absolute rounded-full blur-3xl transition-transform duration-100"
            style={{
              width: 220, height: 220, background: cor.glow,
              transform: `scale(${1 + nivel * 0.7})`,
            }}
          />
          {/* orb */}
          <div
            className={cn(
              "relative flex items-center justify-center rounded-full text-white shadow-2xl transition-transform duration-100",
              estado === "falando" && !mutado && "animate-pulse",
              mutado && "opacity-60 grayscale"
            )}
            style={{
              width: 170, height: 170,
              transform: `scale(${escala})`,
              background: `radial-gradient(circle at 32% 28%, ${cor.de}, ${cor.para})`,
              boxShadow: `0 0 60px ${cor.glow}, inset 0 2px 16px rgba(255,255,255,.25)`,
            }}
          >
            {mutado ? (
              <MicOff size={48} className="opacity-95" />
            ) : estado === "conectando" || estado === "processando" ? (
              <Loader2 size={44} className="animate-spin opacity-90" />
            ) : (
              <Mic size={48} className="opacity-95" />
            )}
          </div>
        </div>

        <div className="flex flex-col items-center gap-1.5">
          <div className="text-xl font-semibold text-ap-text">
            {mutado ? "Microfone mudo" : ROTULO[estado]}
          </div>
          {erro ? (
            <div className="text-sm text-ap-danger">{erro}</div>
          ) : (
            <div className="font-mono text-xs uppercase tracking-widest text-ap-text-faint">
              {mutado
                ? "o APOLO não te ouve — ele continua respondendo"
                : estado === "ouvindo"
                ? "fale à vontade"
                : "chamada de voz · APOLO"}
            </div>
          )}
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onToggleMute}
            className={cn(
              "inline-flex items-center gap-2 rounded-full border px-5 py-3.5 font-semibold transition-all hover:scale-[1.03]",
              mutado
                ? "border-ap-warning/50 bg-ap-warning/15 text-ap-warning"
                : "border-white/15 bg-white/5 text-ap-text hover:bg-white/10"
            )}
            aria-label={mutado ? "Reativar microfone" : "Mutar microfone"}
          >
            {mutado ? <MicOff size={18} /> : <Mic size={18} />}
            {mutado ? "Reativar mic" : "Mutar"}
          </button>
          <button
            onClick={onEncerrar}
            className="inline-flex items-center gap-2.5 rounded-full bg-ap-danger px-6 py-3.5 font-semibold text-white shadow-[0_8px_30px_rgba(255,77,94,.35)] transition-transform hover:scale-105"
          >
            <PhoneOff size={18} />
            Encerrar
          </button>
        </div>
      </div>

      {/* ━━━ transcrição paralela ━━━ */}
      <div className="flex h-1/2 w-full flex-col border-t border-white/10 bg-ap-surface/40 md:h-full md:w-[38%] md:border-l md:border-t-0">
        <div className="border-b border-white/10 px-6 py-4 font-mono text-[11px] uppercase tracking-[0.18em] text-ap-text-faint">
          Transcrição ao vivo
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
          {turnos.length === 0 ? (
            <div className="mt-10 text-center text-sm text-ap-text-faint">
              A conversa aparece aqui conforme vocês falam.
            </div>
          ) : (
            turnos.map((t, i) => (
              <div key={i} className={cn("flex flex-col gap-1", t.papel === "user" ? "items-end" : "items-start")}>
                <span className="font-mono text-[10px] uppercase tracking-widest text-ap-text-faint">
                  {t.papel === "user" ? "Você" : "APOLO"}
                </span>
                <div
                  className={cn(
                    "max-w-[92%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                    t.papel === "user"
                      ? "rounded-br-md bg-ap-blue text-white"
                      : "rounded-bl-md border border-white/10 bg-ap-surface2 text-ap-text"
                  )}
                >
                  {t.texto}
                </div>
              </div>
            ))
          )}
          <div ref={fimRef} />
        </div>
      </div>
    </div>
  );
}
