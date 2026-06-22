import time
from typing import AsyncGenerator
from app.core.logging_config import logger
from app.pipeline.context import TurnContext
from app.pipeline.deps import default_deps
from app.pipeline.errors import ApoloError, TurnFinished
from app.pipeline.events import Token, ErrorEvent, Done
from app.pipeline.stages._util import chunk_text
from app.pipeline.stages import (
    rate_limit, history, classify, authorize,
    generate_sql, assemble_sql, execute_sql, answer,
)

STAGES = [rate_limit, history, classify, authorize, generate_sql, assemble_sql, execute_sql, answer]


async def processar_pergunta(usuario, sessao_id, pergunta, canal="texto") -> AsyncGenerator[dict, None]:
    ctx = TurnContext(usuario=usuario, sessao_id=sessao_id, pergunta=pergunta, canal=canal, t0=time.perf_counter())
    deps = default_deps()
    terminal = "success"
    try:
        for stage in STAGES:
            async for ev in stage.run(ctx, deps):
                yield ev.to_wire()
    except TurnFinished:
        terminal = "finished"
    except ApoloError as e:
        terminal = "error"
        ctx.erro = f"{e.codigo_log}: {e.causa}" if e.causa is not None else (ctx.erro or e.codigo_log)
        logger.error(f"engine.{e.codigo_log}", erro=str(e.causa if e.causa is not None else e.mensagem_amigavel))
        if e.modo == "error_event":
            yield ErrorEvent(e.mensagem_amigavel).to_wire()
        else:
            ctx.resposta_texto = e.mensagem_amigavel
            for ch in chunk_text(e.mensagem_amigavel, 40):
                yield Token(ch).to_wire()

    try:
        await deps.store.save_turn(**ctx.save_kwargs())
    except Exception as e:
        logger.error("engine.persistencia_falhou", erro=str(e))

    if terminal == "success":
        yield Done(ctx.latencia_ms(), tokens=ctx.tokens_dict(), custo_usd=round(ctx.custo, 6)).to_wire()
    elif terminal == "finished":
        yield Done(ctx.latencia_ms(), tokens=ctx.tokens_dict()).to_wire()
    else:
        yield Done(ctx.latencia_ms()).to_wire()
