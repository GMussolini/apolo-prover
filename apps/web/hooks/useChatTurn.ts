"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import { type Mensagem, ETAPAS_INICIAIS } from "@/components/ChatMessage";
import { chatStream, api } from "@/lib/api";
import { useSessao } from "@/lib/sessao-context";
import { aplicarEvento, updateLast } from "@/lib/chat-reducer";

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

export function useChatTurn() {
  const { sessaoId, setSessaoId } = useSessao();
  const [mensagens, setMensagens] = useState<Mensagem[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  // sessão criada por nós no envio atual — o efeito de restauração deve ignorá-la
  // (senão buscaria o histórico ainda vazio e apagaria a mensagem em streaming).
  const sessaoAutocriadaRef = useRef<string | null>(null);

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

        setMensagens((m) => aplicarEvento(m, d));
      }
    } catch (err: any) {
      setMensagens((m) =>
        updateLast(m, { loading: false, etapas: null, texto: `Erro de conexão: ${err.message}` })
      );
    } finally {
      setSending(false);
    }
  }

  function appendMensagem(m: Mensagem) {
    setMensagens((x) => [...x, m]);
  }

  return {
    mensagens,
    input,
    setInput,
    sending,
    enviar,
    dominioAtivo,
    scrollRef,
    appendMensagem,
  };
}
