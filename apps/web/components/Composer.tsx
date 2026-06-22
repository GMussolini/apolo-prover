"use client";

import { Phone, Send, Loader2 } from "lucide-react";

type ComposerProps = {
  input: string;
  setInput: (v: string) => void;
  onEnviar: (e: React.FormEvent) => void;
  sending: boolean;
  onToggleVoz: () => void;
};

export function Composer({ input, setInput, onEnviar, sending, onToggleVoz }: ComposerProps) {
  return (
    <div className="border-t border-white/5 bg-ap-black px-7 pb-5 pt-4">
      <form
        onSubmit={onEnviar}
        className="rounded-2xl border border-white/10 bg-ap-surface px-4 py-3 transition-colors focus-within:border-ap-blue/50"
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onEnviar(e as any);
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
            onClick={onToggleVoz}
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
  );
}
