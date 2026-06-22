import { describe, it, expect } from "vitest";
import {
  updateLast,
  avancarEtapa,
  etapaDoStatus,
  aplicarEvento,
} from "../lib/chat-reducer";
import type { Mensagem, Etapa } from "../components/ChatMessage";

// ── updateLast ────────────────────────────────────────────────────────────────

describe("updateLast", () => {
  it("retorna arr vazio intocado", () => {
    expect(updateLast([], {})).toEqual([]);
  });

  it("aplica patch parcial na última mensagem", () => {
    const msgs: Mensagem[] = [
      { papel: "user", texto: "oi" },
      { papel: "apolo", texto: "", loading: true },
    ];
    const result = updateLast(msgs, { texto: "olá" });
    expect(result[1].texto).toBe("olá");
    expect(result[1].loading).toBe(true); // campo não-patcheado intacto
    expect(result[0]).toBe(msgs[0]); // primeira msg não toca
  });

  it("aceita função como patch", () => {
    const msgs: Mensagem[] = [{ papel: "apolo", texto: "a" }];
    const result = updateLast(msgs, (prev) => ({ texto: prev.texto + "b" }));
    expect(result[0].texto).toBe("ab");
  });

  it("não muta o array original", () => {
    const msgs: Mensagem[] = [{ papel: "apolo", texto: "x" }];
    const result = updateLast(msgs, { texto: "y" });
    expect(msgs[0].texto).toBe("x");
    expect(result).not.toBe(msgs);
  });
});

// ── avancarEtapa ─────────────────────────────────────────────────────────────

describe("avancarEtapa", () => {
  const etapas: Etapa[] = [
    { key: "entendendo", label: "Entendendo", state: "active" },
    { key: "gerando", label: "Gerando", state: "pending" },
    { key: "consultando", label: "Consultando", state: "pending" },
    { key: "respondendo", label: "Respondendo", state: "pending" },
  ];

  it("avança para a etapa correta e marca anteriores como done", () => {
    const result = avancarEtapa(etapas, "gerando");
    expect(result[0].state).toBe("done");
    expect(result[1].state).toBe("active");
    expect(result[2].state).toBe("pending");
    expect(result[3].state).toBe("pending");
  });

  it("retorna o mesmo array se a key não existe", () => {
    const result = avancarEtapa(etapas, "respondendo");
    expect(result[0].state).toBe("done");
    expect(result[1].state).toBe("done");
    expect(result[2].state).toBe("done");
    expect(result[3].state).toBe("active");
  });

  it("não modifica o array original", () => {
    avancarEtapa(etapas, "gerando");
    expect(etapas[0].state).toBe("active");
  });
});

// ── etapaDoStatus ─────────────────────────────────────────────────────────────

describe("etapaDoStatus", () => {
  it("mapeia texto com 'entend' para entendendo", () => {
    expect(etapaDoStatus("Entendendo a pergunta")).toBe("entendendo");
  });

  it("mapeia texto com 'gerando' para gerando", () => {
    expect(etapaDoStatus("Gerando SQL...")).toBe("gerando");
  });

  it("mapeia texto com 'consultando' para consultando", () => {
    expect(etapaDoStatus("Consultando a base")).toBe("consultando");
  });

  it("mapeia texto com 'dados' para consultando", () => {
    expect(etapaDoStatus("Buscando dados")).toBe("consultando");
  });

  it("retorna null para texto irreconhecível", () => {
    expect(etapaDoStatus("outra coisa")).toBeNull();
  });

  it("aceita string vazia sem explodir", () => {
    expect(etapaDoStatus("")).toBeNull();
  });
});

// ── aplicarEvento ─────────────────────────────────────────────────────────────

describe("aplicarEvento", () => {
  const base: Mensagem[] = [
    { papel: "user", texto: "pergunta" },
    { papel: "apolo", texto: "", loading: true, etapas: null, status: null },
  ];

  it("token: acumula delta no texto", () => {
    let msgs = aplicarEvento(base, { type: "token", delta: "a" });
    msgs = aplicarEvento(msgs, { type: "token", delta: "b" });
    expect(msgs[1].texto).toBe("ab");
  });

  it("done: zera loading, etapas e status", () => {
    const withLoading: Mensagem[] = [
      { papel: "apolo", texto: "resposta", loading: true, etapas: [], status: "processando" },
    ];
    const result = aplicarEvento(withLoading, { type: "done" });
    expect(result[0].loading).toBe(false);
    expect(result[0].etapas).toBeNull();
    expect(result[0].status).toBeNull();
    expect(result[0].texto).toBe("resposta"); // texto preservado
  });

  it("classification: aplica dominio e confidence", () => {
    const result = aplicarEvento(base, {
      type: "classification",
      dominio: "crm",
      confidence: 0.95,
    });
    expect(result[1].dominio).toBe("crm");
    expect(result[1].confidence).toBe(0.95);
  });

  it("sql: aplica sql", () => {
    const result = aplicarEvento(base, { type: "sql", sql: "SELECT 1" });
    expect(result[1].sql).toBe("SELECT 1");
  });

  it("chart: aplica grafico_sugerido e spec_grafico", () => {
    const result = aplicarEvento(base, {
      type: "chart",
      tipo: "bar",
      spec: { data: [] },
    });
    expect(result[1].grafico_sugerido).toBe("bar");
    expect(result[1].spec_grafico).toEqual({ data: [] });
  });

  it("error: zera loading/etapas/status e usa mensagem de erro", () => {
    const withLoading: Mensagem[] = [
      { papel: "apolo", texto: "", loading: true, etapas: [], status: "processando" },
    ];
    const result = aplicarEvento(withLoading, {
      type: "error",
      text: "algo deu errado",
    });
    expect(result[0].loading).toBe(false);
    expect(result[0].etapas).toBeNull();
    expect(result[0].status).toBeNull();
    expect(result[0].texto).toBe("algo deu errado");
  });

  it("error: fallback para texto anterior quando não há mensagem de erro", () => {
    const withText: Mensagem[] = [
      { papel: "apolo", texto: "parcial", loading: true, etapas: [] },
    ];
    const result = aplicarEvento(withText, { type: "error" });
    expect(result[0].texto).toBe("parcial");
  });

  it("tipo desconhecido: retorna msgs intocadas", () => {
    const result = aplicarEvento(base, { type: "desconhecido" });
    expect(result).toBe(base);
  });

  it("status: atualiza status e avança etapa quando reconhecida", () => {
    const withEtapas: Mensagem[] = [
      {
        papel: "apolo",
        texto: "",
        loading: true,
        status: null,
        etapas: [
          { key: "entendendo", label: "Entendendo", state: "active" },
          { key: "gerando", label: "Gerando", state: "pending" },
          { key: "consultando", label: "Consultando", state: "pending" },
          { key: "respondendo", label: "Respondendo", state: "pending" },
        ],
      },
    ];
    const result = aplicarEvento(withEtapas, { type: "status", text: "Gerando SQL" });
    expect(result[0].status).toBe("Gerando SQL");
    expect(result[0].etapas![0].state).toBe("done");
    expect(result[0].etapas![1].state).toBe("active");
  });
});
