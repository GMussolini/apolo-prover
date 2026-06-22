import { type Mensagem, type Etapa, type EtapaKey, ETAPAS_INICIAIS } from "@/components/ChatMessage";

export function updateLast(
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

export function avancarEtapa(etapas: Etapa[], key: EtapaKey): Etapa[] {
  const idx = etapas.findIndex((e) => e.key === key);
  if (idx === -1) return etapas;
  return etapas.map((e, i) => ({
    ...e,
    state: i < idx ? "done" : i === idx ? "active" : "pending",
  }));
}

export function etapaDoStatus(texto: string): EtapaKey | null {
  const t = (texto || "").toLowerCase();
  if (t.includes("entend")) return "entendendo";
  if (t.includes("gerando")) return "gerando";
  if (t.includes("consultando") || t.includes("dados")) return "consultando";
  return null;
}

export function aplicarEvento(
  msgs: Mensagem[],
  evt: { type: string; [key: string]: any }
): Mensagem[] {
  if (evt.type === "status") {
    const key = etapaDoStatus(evt.text || "");
    return updateLast(msgs, (prev) => ({
      status: evt.text,
      etapas: key && prev.etapas ? avancarEtapa(prev.etapas, key) : prev.etapas,
    }));
  } else if (evt.type === "classification") {
    return updateLast(msgs, { dominio: evt.dominio, confidence: evt.confidence });
  } else if (evt.type === "sql") {
    return updateLast(msgs, { sql: evt.sql });
  } else if (evt.type === "token") {
    return updateLast(msgs, (prev) => ({
      texto: (prev.texto || "") + (evt.delta || ""),
      etapas: prev.etapas ? avancarEtapa(prev.etapas, "respondendo") : prev.etapas,
    }));
  } else if (evt.type === "chart") {
    return updateLast(msgs, { grafico_sugerido: evt.tipo, spec_grafico: evt.spec });
  } else if (evt.type === "error") {
    return updateLast(msgs, (prev) => ({
      loading: false,
      status: null,
      etapas: null,
      texto: prev.texto || evt.text || evt.message || "Ocorreu um erro ao processar.",
    }));
  } else if (evt.type === "done") {
    return updateLast(msgs, { loading: false, status: null, etapas: null });
  }
  return msgs;
}
