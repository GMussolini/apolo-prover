"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import { Phone, PhoneOff, Send, Loader2 } from "lucide-react";
import {
  ChatMessage,
  type Mensagem,
  type Etapa,
  type EtapaKey,
  ETAPAS_INICIAIS,
} from "./ChatMessage";
import { chatStream, api } from "@/lib/api";
import { useSessao } from "@/lib/sessao-context";
import { RealtimeClient, type RealtimeEvento } from "@/lib/realtime";
import { VoiceCall, type VoiceTurno } from "./VoiceCall";
import { cn } from "@/lib/utils";

type MensagemHistorico = {
  id: string;
  pergunta: string;
  dominio: string | null;
  confidence: number | null;
  origem: "texto" | "voz" | null;
  created_at: string;
  resposta: string | null;
  sql: string | null;
  grafico_sugerido: string | null;
  spec_grafico: any;
};

type VoiceEstado =
  | "idle"
  | "conectando"
  | "ouvindo"
  | "processando"
  | "falando"
  | "erro";

const VOICE_TIMEOUT_MS = 10 * 60 * 1000;

function avancarEtapa(etapas: Etapa[], key: EtapaKey): Etapa[] {
  const idx = etapas.findIndex((e) => e.key === key);
  if (idx === -1) return etapas;
  return etapas.map((e, i) => ({
    ...e,
    state: i < idx ? "done" : i === idx ? "active" : "pending",
  }));
}

function etapaDoStatus(texto: string): EtapaKey | null {
  const t = (texto || "").toLowerCase();
  if (t.includes("entend")) return "entendendo";
  if (t.includes("gerando")) return "gerando";
  if (t.includes("consultando") || t.includes("dados")) return "consultando";
  return null;
}

export function ChatPanel() {
  const { sessaoId, setSessaoId } = useSessao();
  const [mensagens, setMensagens] = useState<Mensagem[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  // sessão criada por nós no envio atual — o efeito de restauração deve ignorá-la
  // (senão buscaria o histórico ainda vazio e apagaria a mensagem em streaming).
  const sessaoAutocriadaRef = useRef<string | null>(null);

  // ─── voz Realtime ───
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

  const dominioAtivo = useMemo(() => {
    for (let i = mensagens.length - 1; i >= 0; i--) {
      if (mensagens[i].papel === "apolo" && mensagens[i].dominio)
        return mensagens[i].dominio!;
    }
    return null;
  }, [mensagens]);

  // auto-scroll
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [mensagens]);

  // restaura historico ao trocar de sessao
  useEffect(() => {
    let cancelado = false;
    if (!sessaoId) {
      setMensagens([]);
      return;
    }
    // sessão recém-criada por nós neste envio: não restaurar (apagaria o stream ao vivo)
    if (sessaoId === sessaoAutocriadaRef.current) {
      sessaoAutocriadaRef.current = null;
      return;
    }
    (async () => {
      try {
        const historico = await api<MensagemHistorico[]>(
          `/api/sessoes/${sessaoId}/mensagens`
        );
        if (cancelado) return;
        const restauradas: Mensagem[] = [];
        for (const h of historico) {
          restauradas.push({
            id: `${h.id}-q`,
            papel: "user",
            texto: h.pergunta,
            origem: h.origem ?? "texto",
          });
          if (h.resposta !== null) {
            restauradas.push({
              id: `${h.id}-a`,
              papel: "apolo",
              texto: h.resposta ?? "",
              dominio: h.dominio,
              confidence: h.confidence,
              sql: h.sql,
              grafico_sugerido: h.grafico_sugerido,
              spec_grafico: h.spec_grafico,
              loading: false,
            });
          }
        }
        setMensagens(restauradas);
      } catch (err) {
        console.error("falha ao restaurar historico", err);
        if (!cancelado) setMensagens([]);
      }
    })();
    return () => {
      cancelado = true;
    };
  }, [sessaoId]);

  // ─── enviar pergunta (texto) ───
  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || sending) return;
    const pergunta = input.trim();
    setInput("");
    setSending(true);

    const userMsg: Mensagem = { papel: "user", texto: pergunta, origem: "texto" };
    const apoloMsg: Mensagem = {
      papel: "apolo",
      texto: "",
      loading: true,
      etapas: ETAPAS_INICIAIS,
    };
    setMensagens((m) => [...m, userMsg, apoloMsg]);

    try {
      for await (const evt of chatStream(pergunta, sessaoId || undefined)) {
        const d = evt.data;
        if (d && d.sessao_id && !sessaoId) {
          sessaoAutocriadaRef.current = d.sessao_id;
          setSessaoId(d.sessao_id);
        }
        if (!d || !d.type) continue;

        if (d.type === "status") {
          const key = etapaDoStatus(d.text || "");
          setMensagens((m) =>
            updateLast(m, (prev) => ({
              status: d.text,
              etapas: key && prev.etapas ? avancarEtapa(prev.etapas, key) : prev.etapas,
            }))
          );
        } else if (d.type === "classification") {
          setMensagens((m) =>
            updateLast(m, { dominio: d.dominio, confidence: d.confidence })
          );
        } else if (d.type === "sql") {
          setMensagens((m) => updateLast(m, { sql: d.sql }));
        } else if (d.type === "token") {
          setMensagens((m) =>
            updateLast(m, (prev) => ({
              texto: (prev.texto || "") + (d.delta || ""),
              etapas: prev.etapas ? avancarEtapa(prev.etapas, "respondendo") : prev.etapas,
            }))
          );
        } else if (d.type === "chart") {
          setMensagens((m) =>
            updateLast(m, { grafico_sugerido: d.tipo, spec_grafico: d.spec })
          );
        } else if (d.type === "error") {
          setMensagens((m) =>
            updateLast(m, (prev) => ({
              loading: false,
              status: null,
              etapas: null,
              texto: prev.texto || d.text || d.message || "Ocorreu um erro ao processar.",
            }))
          );
        } else if (d.type === "done") {
          setMensagens((m) => updateLast(m, { loading: false, status: null, etapas: null }));
        }
      }
    } catch (err: any) {
      setMensagens((m) =>
        updateLast(m, { loading: false, etapas: null, texto: `Erro de conexão: ${err.message}` })
      );
    } finally {
      setSending(false);
    }
  }

  // ─── voz: toggle ligacao ───
  function handleVoiceEvento(evt: RealtimeEvento) {
    if (evt.type === "estado") setVoiceEstado(evt.estado);
    if (evt.type === "nivel") setVoiceNivel(evt.nivel);
    if (evt.type === "erro") {
      setVoiceErro(evt.mensagem);
      setVoiceEstado("erro");
    }
    if (evt.type === "transcript_user") {
      setMensagens((m) => [...m, { papel: "user", texto: evt.texto, origem: "voz" }]);
      setVoiceTurnos((t) => [...t, { papel: "user", texto: evt.texto }]);
    }
    if (evt.type === "transcript_apolo") {
      setMensagens((m) => [
        ...m,
        { papel: "apolo", texto: evt.texto, origem: "voz", loading: false },
      ]);
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

  return (
    <div className="relative flex h-full min-h-0 flex-col bg-ap-black">
      {/* ━━━ header ━━━ */}
      <header className="flex items-center gap-4 border-b border-white/5 px-7 py-4">
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-semibold text-ap-text">
            {mensagens.length > 0 ? "Conversa" : "Nova conversa"}
          </h1>
          <div className="mt-1 flex items-center gap-2 text-xs text-ap-text-faint">
            {dominioAtivo ? (
              <span className="font-mono uppercase tracking-widest text-ap-blue">
                {dominioAtivo}
              </span>
            ) : (
              <span>assistente de dados · Prover Tecnologia</span>
            )}
          </div>
        </div>

        <button
          onClick={toggleVoz}
          className={cn(
            "inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold transition-all",
            voiceAtivo
              ? "border-ap-danger/50 bg-ap-danger/15 text-ap-danger hover:bg-ap-danger/25"
              : "border-ap-blue/50 bg-ap-blue/10 text-ap-blue hover:bg-ap-blue/20 hover:scale-[1.02]"
          )}
          aria-label={voiceAtivo ? "Encerrar chamada" : "Ligar por voz"}
        >
          {voiceEstado === "conectando" ? (
            <Loader2 size={15} className="animate-spin" />
          ) : voiceAtivo ? (
            <>
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ap-danger opacity-75" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-ap-danger" />
              </span>
              <PhoneOff size={15} />
            </>
          ) : (
            <Phone size={15} />
          )}
          {voiceAtivo && voiceEstado !== "conectando" ? "Encerrar" : voiceLabel[voiceEstado]}
        </button>
      </header>

      {voiceErro && (
        <div className="border-b border-ap-danger/20 bg-ap-danger/10 px-7 py-2 text-xs text-ap-danger">
          {voiceErro}
        </div>
      )}

      {/* ━━━ thread ━━━ */}
      <div ref={scrollRef} className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto px-7 py-6">
        {mensagens.length === 0 ? (
          <div className="m-auto max-w-md px-5 py-16 text-center">
            <div className="mb-3 font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-ap-text-faint">
              Pronto para responder
            </div>
            <div className="mb-2.5 text-xl font-bold text-ap-text">
              Pergunte sobre o CRM e o financeiro.
            </div>
            <div className="text-[13px] leading-relaxed text-ap-text-faint">
              Ex.: "quantos leads o Felipe tem em prospecção?" · "clientes em fase
              Proposta há mais de 30 dias" · "contas a pagar deste mês"
            </div>
          </div>
        ) : (
          mensagens.map((m, i) => <ChatMessage key={m.id ?? i} msg={m} />)
        )}
      </div>

      {/* ━━━ composer ━━━ */}
      <div className="border-t border-white/5 bg-ap-black px-7 pb-5 pt-4">
        <form
          onSubmit={enviar}
          className="rounded-2xl border border-white/10 bg-ap-surface px-4 py-3 transition-colors focus-within:border-ap-blue/50"
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                enviar(e as any);
              }
            }}
            placeholder="Pergunte algo — ex: quantos leads o Felipe tem?"
            rows={1}
            className="min-h-[28px] w-full resize-none bg-transparent text-sm text-ap-text outline-none placeholder:text-ap-text-faint"
            disabled={sending}
          />
          <div className="mt-2.5 flex items-center gap-2 border-t border-white/5 pt-2.5">
            <span className="font-mono text-[11px] text-ap-text-faint">
              Shift + ⏎ quebra linha
            </span>
            <button
              type="button"
              onClick={toggleVoz}
              className="ml-auto inline-flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-ap-surface2 text-ap-text-muted transition-colors hover:bg-ap-surface3 hover:text-ap-text"
              aria-label="Conversar por voz"
            >
              <Phone size={14} />
            </button>
            <button
              type="submit"
              disabled={!input.trim() || sending}
              className="inline-flex items-center gap-2 rounded-lg bg-ap-blue px-4 py-2 text-sm font-semibold text-white transition-all hover:bg-ap-blue-hover disabled:cursor-not-allowed disabled:opacity-40"
            >
              {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              Enviar
            </button>
          </div>
        </form>
        <div className="mt-2.5 text-center font-mono text-[10px] uppercase tracking-[0.12em] text-ap-text-faint">
          APOLO consulta as bases em modo leitura · confirme números críticos na fonte
        </div>
      </div>

      {voiceAtivo && (
        <VoiceCall
          estado={voiceEstado}
          nivel={voiceMutado ? 0 : voiceNivel}
          turnos={voiceTurnos}
          erro={voiceErro}
          mutado={voiceMutado}
          onToggleMute={toggleMute}
          onEncerrar={toggleVoz}
        />
      )}

      <audio ref={audioRef} autoPlay className="hidden" />
    </div>
  );
}

function updateLast(
  arr: Mensagem[],
  patch: Partial<Mensagem> | ((prev: Mensagem) => Partial<Mensagem>)
): Mensagem[] {
  if (arr.length === 0) return arr;
  const copy = [...arr];
  const prev = copy[copy.length - 1];
  const p = typeof patch === "function" ? patch(prev) : patch;
  copy[copy.length - 1] = { ...prev, ...p };
  return copy;
}
