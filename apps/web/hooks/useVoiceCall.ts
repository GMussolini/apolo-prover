"use client";

import { useState, useRef, useEffect } from "react";
import { type Mensagem } from "@/components/ChatMessage";
import { RealtimeClient, type RealtimeEvento } from "@/lib/realtime";
import { type VoiceTurno } from "@/components/VoiceCall";

type VoiceEstado =
  | "idle"
  | "conectando"
  | "ouvindo"
  | "processando"
  | "falando"
  | "erro";

const VOICE_TIMEOUT_MS = 10 * 60 * 1000;

export function useVoiceCall({
  onAppendMensagem,
}: {
  onAppendMensagem: (m: Mensagem) => void;
}) {
  const [voiceEstado, setVoiceEstado] = useState<VoiceEstado>("idle");
  const [voiceErro, setVoiceErro] = useState<string | null>(null);
  const [voiceNivel, setVoiceNivel] = useState(0);
  const [voiceTurnos, setVoiceTurnos] = useState<VoiceTurno[]>([]);
  const [voiceMutado, setVoiceMutado] = useState(false);
  const voiceClientRef = useRef<RealtimeClient | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const voiceTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const voiceAtivo =
    voiceEstado === "conectando" ||
    voiceEstado === "ouvindo" ||
    voiceEstado === "processando" ||
    voiceEstado === "falando";

  function handleVoiceEvento(evt: RealtimeEvento) {
    if (evt.type === "estado") setVoiceEstado(evt.estado);
    if (evt.type === "nivel") setVoiceNivel(evt.nivel);
    if (evt.type === "erro") {
      setVoiceErro(evt.mensagem);
      setVoiceEstado("erro");
    }
    if (evt.type === "transcript_user") {
      onAppendMensagem({ papel: "user", texto: evt.texto, origem: "voz" });
      setVoiceTurnos((t) => [...t, { papel: "user", texto: evt.texto }]);
    }
    if (evt.type === "transcript_apolo") {
      onAppendMensagem({ papel: "apolo", texto: evt.texto, origem: "voz", loading: false });
      setVoiceTurnos((t) => [...t, { papel: "apolo", texto: evt.texto }]);
    }
  }

  async function toggleVoz() {
    if (!voiceAtivo) {
      setVoiceErro(null);
      setVoiceTurnos([]);
      setVoiceNivel(0);
      setVoiceMutado(false);
      const client = new RealtimeClient(handleVoiceEvento);
      voiceClientRef.current = client;
      try {
        await client.iniciar(audioRef.current!);
        voiceTimeoutRef.current = setTimeout(() => client.parar(), VOICE_TIMEOUT_MS);
      } catch (e: any) {
        setVoiceErro(e.message);
        setVoiceEstado("erro");
      }
    } else {
      await voiceClientRef.current?.parar();
      if (voiceTimeoutRef.current) clearTimeout(voiceTimeoutRef.current);
      setVoiceEstado("idle");
    }
  }

  useEffect(
    () => () => {
      voiceClientRef.current?.parar();
      if (voiceTimeoutRef.current) clearTimeout(voiceTimeoutRef.current);
    },
    []
  );

  function toggleMute() {
    const novo = !voiceMutado;
    setVoiceMutado(novo);
    voiceClientRef.current?.mutar(novo);
  }

  const voiceLabel: Record<VoiceEstado, string> = {
    idle: "Ligar",
    conectando: "Conectando…",
    ouvindo: "Ouvindo",
    processando: "Processando",
    falando: "Falando",
    erro: "Tentar de novo",
  };

  return {
    voiceEstado,
    voiceErro,
    voiceNivel,
    voiceTurnos,
    voiceMutado,
    voiceAtivo,
    toggleVoz,
    toggleMute,
    audioRef,
    voiceLabel,
  };
}
