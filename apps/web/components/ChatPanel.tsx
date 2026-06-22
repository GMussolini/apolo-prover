"use client";

import { Phone, PhoneOff, Loader2 } from "lucide-react";
import { ChatMessage } from "./ChatMessage";
import { VoiceCall } from "./VoiceCall";
import { Composer } from "./Composer";
import { useChatTurn } from "@/hooks/useChatTurn";
import { useVoiceCall } from "@/hooks/useVoiceCall";
import { cn } from "@/lib/utils";

export function ChatPanel() {
  const chat = useChatTurn();
  const voice = useVoiceCall({ onAppendMensagem: chat.appendMensagem });

  return (
    <div className="relative flex h-full min-h-0 flex-col bg-ap-black">
      {/* ━━━ header ━━━ */}
      <header className="flex items-center gap-4 border-b border-white/5 px-7 py-4">
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-semibold text-ap-text">
            {chat.mensagens.length > 0 ? "Conversa" : "Nova conversa"}
          </h1>
          <div className="mt-1 flex items-center gap-2 text-xs text-ap-text-faint">
            {chat.dominioAtivo ? (
              <span className="font-mono uppercase tracking-widest text-ap-blue">
                {chat.dominioAtivo}
              </span>
            ) : (
              <span>assistente de dados · Prover Tecnologia</span>
            )}
          </div>
        </div>

        <button
          onClick={voice.toggleVoz}
          className={cn(
            "inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold transition-all",
            voice.voiceAtivo
              ? "border-ap-danger/50 bg-ap-danger/15 text-ap-danger hover:bg-ap-danger/25"
              : "border-ap-blue/50 bg-ap-blue/10 text-ap-blue hover:bg-ap-blue/20 hover:scale-[1.02]"
          )}
          aria-label={voice.voiceAtivo ? "Encerrar chamada" : "Ligar por voz"}
        >
          {voice.voiceEstado === "conectando" ? (
            <Loader2 size={15} className="animate-spin" />
          ) : voice.voiceAtivo ? (
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
          {voice.voiceAtivo && voice.voiceEstado !== "conectando" ? "Encerrar" : voice.voiceLabel[voice.voiceEstado]}
        </button>
      </header>

      {voice.voiceErro && (
        <div className="border-b border-ap-danger/20 bg-ap-danger/10 px-7 py-2 text-xs text-ap-danger">
          {voice.voiceErro}
        </div>
      )}

      {/* ━━━ thread ━━━ */}
      <div ref={chat.scrollRef} className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto px-7 py-6">
        {chat.mensagens.length === 0 ? (
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
          chat.mensagens.map((m, i) => <ChatMessage key={m.id ?? i} msg={m} />)
        )}
      </div>

      {/* ━━━ composer ━━━ */}
      <Composer
        input={chat.input}
        setInput={chat.setInput}
        onEnviar={chat.enviar}
        sending={chat.sending}
        onToggleVoz={voice.toggleVoz}
      />

      {voice.voiceAtivo && (
        <VoiceCall
          estado={voice.voiceEstado}
          nivel={voice.voiceMutado ? 0 : voice.voiceNivel}
          turnos={voice.voiceTurnos}
          erro={voice.voiceErro}
          mutado={voice.voiceMutado}
          onToggleMute={voice.toggleMute}
          onEncerrar={voice.toggleVoz}
        />
      )}

      <audio ref={voice.audioRef} autoPlay className="hidden" />
    </div>
  );
}
