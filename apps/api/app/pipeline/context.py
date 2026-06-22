import time
from dataclasses import dataclass, field


@dataclass
class TurnContext:
    usuario: dict
    sessao_id: str
    pergunta: str
    canal: str
    t0: float
    tokens_input: int = 0
    tokens_output: int = 0
    custo: float = 0.0
    pergunta_reformulada: str | None = None
    dominio_nome: str | None = None
    base_conexao: str | None = None
    confidence: float | None = None
    sql_gerado: str | None = None
    dados_retornados: list | None = None
    resposta_texto: str | None = None
    grafico_sugerido: str | None = None
    spec_grafico: dict | None = None
    erro: str | None = None

    # campos de trabalho (transientes, passados entre estágios)
    historico_txt: str = "(sem histórico)"
    dominio: object | None = None
    partes: dict | None = None
    amostra: list | None = None
    total_linhas: int = 0

    def add_usage(self, ti: int, to: int, custo: float) -> None:
        self.tokens_input += ti
        self.tokens_output += to
        self.custo += custo

    def latencia_ms(self) -> int:
        return int((time.perf_counter() - self.t0) * 1000)

    def tokens_dict(self) -> dict:
        return {"input": self.tokens_input, "output": self.tokens_output}

    def save_kwargs(self) -> dict:
        return {
            "sessao_id": self.sessao_id,
            "usuario_id": self.usuario["id"],
            "pergunta": self.pergunta,
            "pergunta_reformulada": self.pergunta_reformulada,
            "dominio_nome": self.dominio_nome,
            "base_conexao": self.base_conexao,
            "confidence": round(self.confidence, 2) if self.confidence is not None else None,
            "canal": self.canal,
            "resposta_texto": self.resposta_texto,
            "sql_gerado": self.sql_gerado,
            "dados_retornados": self.dados_retornados,
            "grafico_sugerido": self.grafico_sugerido,
            "spec_grafico": self.spec_grafico,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "custo_estimado": round(self.custo, 6),
            "latencia_ms": self.latencia_ms(),
            "erro": self.erro,
        }
