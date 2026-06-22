"""Engine APOLO — orquestra as 6 etapas da abordagem híbrida.

Fluxo:
1. Rate limit
2. Histórico (últimas 5 perguntas/respostas) carregado do Postgres
3. Classificação de intenção (Claude — sonnet) -> escolhe domínio
4. Permissão (RBAC sobre permissoes_necessarias do domínio)
5. Geração de SQL (Claude — sonnet) -> partes JSON -> pipeline.montar_sql_final
6. Execução em SQL Server (read-only) + geração de resposta (Claude — haiku)

Yields chunks SSE: status, sql, token, chart, done, error.
"""
import json
import time
import uuid
from typing import AsyncGenerator

import pandas as pd
from fastapi import HTTPException

from app.core.config import get_config
from app.core.database import execute_query, get_pg_pool
from app.core.logging_config import logger
from app.core.permissoes import usuario_pode
from app.core.rate_limiter import consumir_pergunta
from app.core.sql_guard import SqlNaoPermitidoError
from app.domains import REGISTRY, listar_ativos
from app.pipeline.deps import default_deps
from app.services import anthropic_service, prompts_service
from app.services import pipeline as pipe


# ============================================================
# Helpers internos
# ============================================================

async def _carregar_historico(sessao_id: str, limite: int = 5) -> list[tuple[str, str]]:
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


def _format_historico(rows: list[tuple[str, str]]) -> str:
    if not rows:
        return "(sem histórico)"
    blocos = []
    for i, (pergunta, resposta) in enumerate(rows, 1):
        resp = (resposta or "").strip()
        if len(resp) > 400:
            resp = resp[:400] + "..."
        blocos.append(f"[{i}] Usuário: {pergunta}\n    APOLO: {resp or '(sem resposta)'}")
    return "\n".join(blocos)


def _chunk_text(text: str, size: int = 40):
    """Itera o texto em pedaços de até `size` chars."""
    if not text:
        return
    for i in range(0, len(text), size):
        yield text[i:i + size]


def _df_para_amostra(df: pd.DataFrame, max_linhas: int) -> tuple[list[dict], int]:
    """Converte DataFrame em lista de dicts JSON-safe + retorna total."""
    total = len(df)
    if total == 0:
        return [], 0
    amostra = df.head(max_linhas).copy()
    # normaliza tipos não-serializáveis (datetime/decimal/etc)
    for c in amostra.columns:
        if pd.api.types.is_datetime64_any_dtype(amostra[c]):
            amostra[c] = amostra[c].astype(str)
    return json.loads(amostra.to_json(orient="records", date_format="iso", default_handler=str)), total


async def _salvar_pergunta_resposta(
    *,
    sessao_id: str,
    usuario_id: int,
    pergunta: str,
    pergunta_reformulada: str | None,
    dominio_nome: str | None,
    base_conexao: str | None,
    confidence: float | None,
    canal: str,
    resposta_texto: str | None,
    sql_gerado: str | None,
    dados_retornados: list[dict] | None,
    grafico_sugerido: str | None,
    spec_grafico: dict | None,
    tokens_input: int,
    tokens_output: int,
    custo_estimado: float,
    latencia_ms: int,
    erro: str | None,
) -> None:
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


# ============================================================
# Orquestrador principal
# ============================================================

async def processar_pergunta(
    usuario: dict,
    sessao_id: str,
    pergunta: str,
    canal: str = "texto",
) -> AsyncGenerator[dict, None]:
    """Stream de eventos SSE do ciclo completo da pergunta.

    Cada yield é um dict com chave `type` ∈ {status, sql, token, chart, done, error}.
    """
    deps = default_deps()
    cfg = deps.cfg
    t0 = time.perf_counter()

    tokens_input_total = 0
    tokens_output_total = 0
    custo_total = 0.0

    # Snapshot pra persistência ao final ou em erro
    estado = {
        "pergunta_reformulada": None,
        "dominio_nome": None,
        "base_conexao": None,
        "confidence": None,
        "sql_gerado": None,
        "dados_retornados": None,
        "resposta_texto": None,
        "grafico_sugerido": None,
        "spec_grafico": None,
        "erro": None,
    }

    async def _persistir():
        try:
            await deps.store.save_turn(
                sessao_id=sessao_id,
                usuario_id=usuario["id"],
                pergunta=pergunta,
                pergunta_reformulada=estado["pergunta_reformulada"],
                dominio_nome=estado["dominio_nome"],
                base_conexao=estado["base_conexao"],
                confidence=estado["confidence"],
                canal=canal,
                resposta_texto=estado["resposta_texto"],
                sql_gerado=estado["sql_gerado"],
                dados_retornados=estado["dados_retornados"],
                grafico_sugerido=estado["grafico_sugerido"],
                spec_grafico=estado["spec_grafico"],
                tokens_input=tokens_input_total,
                tokens_output=tokens_output_total,
                custo_estimado=round(custo_total, 6),
                latencia_ms=int((time.perf_counter() - t0) * 1000),
                erro=estado["erro"],
            )
        except Exception as e:
            logger.error("engine.persistencia_falhou", erro=str(e))

    # ------------------------------------------------------------
    # 1) Rate limit
    # ------------------------------------------------------------
    try:
        await consumir_pergunta(usuario["id"])
    except HTTPException as e:
        estado["erro"] = f"rate_limit: {e.detail}"
        yield {"type": "error", "text": str(e.detail)}
        await _persistir()
        yield {"type": "done", "latencia_ms": int((time.perf_counter() - t0) * 1000)}
        return

    yield {"type": "status", "text": "Entendendo sua pergunta..."}

    # ------------------------------------------------------------
    # 2) Histórico
    # ------------------------------------------------------------
    historico_rows = await deps.store.load_history(sessao_id, limite=5)
    historico_txt = _format_historico(historico_rows)

    # ------------------------------------------------------------
    # 3) Classificação
    # ------------------------------------------------------------
    dominios = listar_ativos()
    ctx_clf = pipe.contexto_para_classificador(dominios, pergunta)
    prompt_clf = prompts_service.render(
        "intent_classification",
        lista_dominios=ctx_clf["lista_dominios"],
        sinais_lexicais=ctx_clf["sinais_lexicais"],
        historico=historico_txt,
        pergunta=pergunta,
    )

    try:
        clf = await deps.llm.chat_json(
            modelo=cfg.model_classificador,
            system=prompt_clf,
            user=pergunta,
            max_tokens=600,
            temperatura=0.0,
        )
    except Exception as e:
        logger.error("engine.classificador_falhou", erro=str(e))
        estado["erro"] = f"classificador: {e}"
        yield {"type": "error", "text": "Não consegui entender sua pergunta. Tente reformular."}
        await _persistir()
        yield {"type": "done", "latencia_ms": int((time.perf_counter() - t0) * 1000)}
        return

    tokens_input_total += clf["tokens_input"]
    tokens_output_total += clf["tokens_output"]
    custo_total += deps.llm.estimar_custo(
        cfg.model_classificador, clf["tokens_input"], clf["tokens_output"]
    )

    data_clf = clf["data"] or {}
    dominio_nome = data_clf.get("dominio")
    confidence = float(data_clf.get("confidence") or 0.0)
    pergunta_reform = data_clf.get("pergunta_reformulada") or pergunta
    refinamento = data_clf.get("refinamento")

    estado["pergunta_reformulada"] = pergunta_reform
    estado["dominio_nome"] = dominio_nome
    estado["confidence"] = round(confidence, 2)

    if not dominio_nome or confidence < 0.5 or dominio_nome not in REGISTRY:
        msg = refinamento or "Sua pergunta está muito ampla. Pode detalhar?"
        estado["resposta_texto"] = msg
        for ch in _chunk_text(msg, 40):
            yield {"type": "token", "delta": ch}
        await _persistir()
        yield {
            "type": "done",
            "latencia_ms": int((time.perf_counter() - t0) * 1000),
            "tokens": {"input": tokens_input_total, "output": tokens_output_total},
        }
        return

    dominio = REGISTRY[dominio_nome]
    estado["base_conexao"] = dominio.base_conexao
    yield {"type": "classification", "dominio": dominio_nome, "confidence": round(confidence, 2)}

    # ------------------------------------------------------------
    # 4) Permissão
    # ------------------------------------------------------------
    if not usuario_pode(
        usuario.get("permissoes", "") or "",
        dominio.permissoes_necessarias,
        usuario.get("is_admin", False),
    ):
        msg = (
            f"Você não tem permissão para acessar o domínio **{dominio_nome}**. "
            "Fale com o administrador se precisar de acesso."
        )
        estado["resposta_texto"] = msg
        estado["erro"] = "permissao_negada"
        for ch in _chunk_text(msg, 40):
            yield {"type": "token", "delta": ch}
        await _persistir()
        yield {
            "type": "done",
            "latencia_ms": int((time.perf_counter() - t0) * 1000),
            "tokens": {"input": tokens_input_total, "output": tokens_output_total},
        }
        return

    yield {"type": "status", "text": "Gerando consulta..."}

    # ------------------------------------------------------------
    # 5) SQL Generator (híbrido)
    # ------------------------------------------------------------
    ctx_sql = pipe.contexto_para_sql_generator(dominio, pergunta_reform)
    prompt_sql = prompts_service.render("sql_generator", **ctx_sql)

    try:
        sqlgen = await deps.llm.chat_json(
            modelo=cfg.model_sql_generator,
            system=prompt_sql,
            user=pergunta_reform,
            max_tokens=1500,
            temperatura=0.0,
        )
    except Exception as e:
        logger.error("engine.sql_generator_falhou", erro=str(e))
        estado["erro"] = f"sql_generator: {e}"
        msg = "Tive um problema gerando a consulta. Tente reformular a pergunta."
        estado["resposta_texto"] = msg
        for ch in _chunk_text(msg, 40):
            yield {"type": "token", "delta": ch}
        await _persistir()
        yield {"type": "done", "latencia_ms": int((time.perf_counter() - t0) * 1000)}
        return

    tokens_input_total += sqlgen["tokens_input"]
    tokens_output_total += sqlgen["tokens_output"]
    custo_total += deps.llm.estimar_custo(
        cfg.model_sql_generator, sqlgen["tokens_input"], sqlgen["tokens_output"]
    )

    partes = sqlgen["data"] or {}
    try:
        sql_final = pipe.montar_sql_final(dominio, partes)
    except SqlNaoPermitidoError as e:
        logger.error("engine.sql_invalido", erro=str(e))
        estado["erro"] = f"sql_invalido: {e}"
        msg = "A consulta gerada foi bloqueada por segurança. Tente reformular."
        estado["resposta_texto"] = msg
        for ch in _chunk_text(msg, 40):
            yield {"type": "token", "delta": ch}
        await _persistir()
        yield {"type": "done", "latencia_ms": int((time.perf_counter() - t0) * 1000)}
        return
    except Exception as e:
        logger.error("engine.montar_sql_falhou", erro=str(e))
        estado["erro"] = f"montar_sql: {e}"
        msg = "Não consegui montar a consulta. Tente reformular."
        estado["resposta_texto"] = msg
        for ch in _chunk_text(msg, 40):
            yield {"type": "token", "delta": ch}
        await _persistir()
        yield {"type": "done", "latencia_ms": int((time.perf_counter() - t0) * 1000)}
        return

    estado["sql_gerado"] = sql_final
    yield {"type": "sql", "sql": sql_final}

    # ------------------------------------------------------------
    # 6) Execução + resposta
    # ------------------------------------------------------------
    yield {"type": "status", "text": "Consultando dados..."}

    try:
        df = await deps.sql.execute_query(
            dominio.base_conexao,
            sql_final,
            timeout=cfg.sql_query_timeout_seconds,
        )
    except Exception as e:
        logger.error("engine.execucao_sql_falhou", erro=str(e))
        estado["erro"] = f"execucao_sql: {e}"
        msg = "Não consegui consultar a base no momento. Tente de novo em instantes."
        estado["resposta_texto"] = msg
        for ch in _chunk_text(msg, 40):
            yield {"type": "token", "delta": ch}
        await _persistir()
        yield {"type": "done", "latencia_ms": int((time.perf_counter() - t0) * 1000)}
        return

    amostra, total_linhas = _df_para_amostra(df, cfg.max_linhas_amostra)
    # Trunca dados persistidos pra não estourar JSONB
    dados_persistir = amostra[: cfg.max_linhas_dados_retornados]
    estado["dados_retornados"] = dados_persistir

    yield {"type": "status", "text": "Montando resposta..."}

    if canal == "voz":
        prompt_voz = prompts_service.render(
            "response_voice",
            pergunta=pergunta_reform,
            sql=sql_final,
            dados_amostra_json=json.dumps(amostra, ensure_ascii=False),
            total_linhas=total_linhas,
        )
        try:
            resp = await deps.llm.chat_texto(
                modelo=cfg.model_response_voice,
                system=prompt_voz,
                user=pergunta_reform,
                max_tokens=400,
                temperatura=0.3,
            )
        except Exception as e:
            logger.error("engine.response_voice_falhou", erro=str(e))
            estado["erro"] = f"response_voice: {e}"
            msg = "Consegui os dados, mas falhei em narrar. Tente de novo."
            estado["resposta_texto"] = msg
            for ch in _chunk_text(msg, 40):
                yield {"type": "token", "delta": ch}
            await _persistir()
            yield {"type": "done", "latencia_ms": int((time.perf_counter() - t0) * 1000)}
            return

        tokens_input_total += resp["tokens_input"]
        tokens_output_total += resp["tokens_output"]
        custo_total += deps.llm.estimar_custo(
            cfg.model_response_voice, resp["tokens_input"], resp["tokens_output"]
        )

        texto = resp["texto"]
        estado["resposta_texto"] = texto
        for ch in _chunk_text(texto, 40):
            yield {"type": "token", "delta": ch}

    else:
        prompt_resp = prompts_service.render(
            "response_generator",
            pergunta=pergunta_reform,
            sql=sql_final,
            max_linhas=cfg.max_linhas_amostra,
            dados_amostra_json=json.dumps(amostra, ensure_ascii=False),
            total_linhas=total_linhas,
        )
        try:
            resp = await deps.llm.chat_json(
                modelo=cfg.model_response_text,
                system=prompt_resp,
                user=pergunta_reform,
                max_tokens=1500,
                temperatura=0.2,
            )
        except Exception as e:
            logger.error("engine.response_generator_falhou", erro=str(e))
            estado["erro"] = f"response_generator: {e}"
            msg = "Consegui os dados, mas falhei em formatar a resposta. Tente de novo."
            estado["resposta_texto"] = msg
            for ch in _chunk_text(msg, 40):
                yield {"type": "token", "delta": ch}
            await _persistir()
            yield {"type": "done", "latencia_ms": int((time.perf_counter() - t0) * 1000)}
            return

        tokens_input_total += resp["tokens_input"]
        tokens_output_total += resp["tokens_output"]
        custo_total += deps.llm.estimar_custo(
            cfg.model_response_text, resp["tokens_input"], resp["tokens_output"]
        )

        data_resp = resp["data"] or {}
        texto = (data_resp.get("resposta") or "").strip()
        grafico = data_resp.get("grafico_sugerido")
        spec = data_resp.get("spec_grafico")

        estado["resposta_texto"] = texto
        estado["grafico_sugerido"] = grafico
        estado["spec_grafico"] = spec

        for ch in _chunk_text(texto, 40):
            yield {"type": "token", "delta": ch}

        if grafico and spec:
            yield {"type": "chart", "tipo": grafico, "spec": spec}

    # ------------------------------------------------------------
    # 7) Persistência + done
    # ------------------------------------------------------------
    await _persistir()
    yield {
        "type": "done",
        "latencia_ms": int((time.perf_counter() - t0) * 1000),
        "tokens": {"input": tokens_input_total, "output": tokens_output_total},
        "custo_usd": round(custo_total, 6),
    }
