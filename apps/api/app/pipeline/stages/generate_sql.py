from app.services import prompts_service
from app.services import pipeline as pipe
from app.pipeline.errors import SqlGenFailed


async def run(ctx, deps):
    ctx_sql = pipe.contexto_para_sql_generator(ctx.dominio, ctx.pergunta_reformulada)
    prompt_sql = prompts_service.render("sql_generator", **ctx_sql)
    try:
        sqlgen = await deps.llm.chat_json(
            modelo=deps.cfg.model_sql_generator, system=prompt_sql,
            user=ctx.pergunta_reformulada, max_tokens=1500, temperatura=0.0,
        )
    except Exception as e:
        raise SqlGenFailed(e)
    ctx.add_usage(
        sqlgen["tokens_input"], sqlgen["tokens_output"],
        deps.llm.estimar_custo(deps.cfg.model_sql_generator, sqlgen["tokens_input"], sqlgen["tokens_output"]),
    )
    ctx.partes = sqlgen["data"] or {}
    return
    yield
