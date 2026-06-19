"use client";

import { useState, useRef, useEffect } from "react";
import { RealtimeClient, type RealtimeEvento } from "@/lib/realtime";
import { cn } from "@/lib/utils";

const TIMEOUT_MS = 10 * 60 * 1000;

type Estado = "idle" | "conectando" | "ouvindo" | "processando" | "falando" | "erro";

export function VoiceBubble({
  onTranscript,
}: {
  onTranscript: (papel: "user" | "apolo", texto: string) => void;
}) {
  const [estado, setEstado] = useState<Estado>("idle");
  const [erro, setErro] = useState<string | null>(null);
  const clientRef = useRef<RealtimeClient | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleEvento(evt: RealtimeEvento) {
    if (evt.type === "estado") setEstado(evt.estado);
    if (evt.type === "transcript_user") onTranscript("user", evt.texto);
    if (evt.type === "transcript_apolo") onTranscript("apolo", evt.texto);
    if (evt.type === "erro") setErro(evt.mensagem);
  }

  async function toggle() {
    if (estado === "idle" || estado === "erro") {
      setErro(null);
      const client = new RealtimeClient(handleEvento);
      clientRef.current = client;
      try {
        await client.iniciar(audioRef.current!);
        timeoutRef.current = setTimeout(() => client.parar(), TIMEOUT_MS);
      } catch (e: any) {
        setErro(e.message);
        setEstado("erro");
      }
    } else {
      await clientRef.current?.parar();
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    }
  }

  useEffect(() => () => {
    clientRef.current?.parar();
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
  }, []);

  const cor = {
    idle: "bg-ap-blue/20 border-ap-blue/40",
    conectando: "bg-ap-warning/20 border-ap-warning/40 animate-pulse",
    ouvindo: "bg-ap-success/20 border-ap-success/60 animate-pulse",
    processando: "bg-ap-info/20 border-ap-info/40 animate-spin-slow",
    falando: "bg-ap-blue/40 border-ap-blue animate-pulse",
    erro: "bg-ap-danger/20 border-ap-danger/40",
  }[estado];

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-2">
      {erro && <p className="text-xs text-ap-danger bg-ap-surface px-3 py-1 rounded">{erro}</p>}
      <button
        onClick={toggle}
        className={cn(
          "w-14 h-14 rounded-full border-2 flex items-center justify-center transition-all hover:scale-105",
          cor
        )}
        aria-label="voz"
      >
        <span className="text-2xl">{estado === "idle" || estado === "erro" ? "🎙️" : "⏸️"}</span>
      </button>
      <audio ref={audioRef} autoPlay />
    </div>
  );
}
