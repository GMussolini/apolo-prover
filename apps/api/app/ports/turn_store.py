import json
from typing import Protocol
from app.core.database import get_pg_pool


class TurnStorePort(Protocol):
    async def load_history(self, sessao_id: str, limite: int = 5) -> list[tuple[str, str]]: ...
    async def save_turn(self, **kwargs) -> None: ...


class PgTurnStore:
    async def load_history(self, sessao_id: str, limite: int = 5) -> list[tuple[str, str]]:
        """Carrega últimas (pergunta, resposta_texto) da sessão em ordem cronológica asc."""
        if not sessao_id:
            return []
        pool = get_pg_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT p.pergunta, COALESCE(r.resposta_texto, '')
                    FROM tb_pergunta p
                    LEFT JOIN tb_resposta r ON r.pergunta_id = p.id
                    WHERE p.sessao_id = %s
                    ORDER BY p.created_at DESC
                    LIMIT %s
                    """,
                    (sessao_id, limite),
                )
                rows = await cur.fetchall()
        # devolver em ordem cronológica (mais antiga primeiro)
        return [(p, r) for p, r in reversed(rows)]

    async def save_turn(self, **kwargs) -> None:
        sessao_id = kwargs["sessao_id"]
        usuario_id = kwargs["usuario_id"]
        pergunta = kwargs["pergunta"]
        pergunta_reformulada = kwargs["pergunta_reformulada"]
        dominio_nome = kwargs["dominio_nome"]
        base_conexao = kwargs["base_conexao"]
        confidence = kwargs["confidence"]
        canal = kwargs["canal"]
        resposta_texto = kwargs["resposta_texto"]
        sql_gerado = kwargs["sql_gerado"]
        dados_retornados = kwargs["dados_retornados"]
        grafico_sugerido = kwargs["grafico_sugerido"]
        spec_grafico = kwargs["spec_grafico"]
        tokens_input = kwargs["tokens_input"]
        tokens_output = kwargs["tokens_output"]
        custo_estimado = kwargs["custo_estimado"]
        latencia_ms = kwargs["latencia_ms"]
        erro = kwargs["erro"]

        pool = get_pg_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO tb_pergunta
                      (sessao_id, usuario_id, pergunta, pergunta_reformulada,
                       dominio, base_conexao, confidence_classificacao, origem)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        sessao_id, usuario_id, pergunta, pergunta_reformulada,
                        dominio_nome, base_conexao, confidence, canal,
                    ),
                )
                pergunta_id = (await cur.fetchone())[0]

                await cur.execute(
                    """
                    INSERT INTO tb_resposta
                      (pergunta_id, resposta_texto, sql_gerado, dados_retornados,
                       grafico_sugerido, spec_grafico, tokens_input, tokens_output,
                       custo_estimado, latencia_ms, erro)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        pergunta_id,
                        resposta_texto,
                        sql_gerado,
                        json.dumps(dados_retornados) if dados_retornados is not None else None,
                        grafico_sugerido,
                        json.dumps(spec_grafico) if spec_grafico is not None else None,
                        tokens_input,
                        tokens_output,
                        custo_estimado,
                        latencia_ms,
                        erro,
                    ),
                )

                await cur.execute(
                    "UPDATE tb_sessao SET updated_at = NOW() WHERE id = %s",
                    (sessao_id,),
                )
            await conn.commit()
