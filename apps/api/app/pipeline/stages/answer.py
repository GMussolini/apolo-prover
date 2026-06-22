import json
from app.services import prompts_service
from app.pipeline.errors import AnswerFailed
from app.pipeline.events import Token, Chart
from app.pipeline.stages._util import chunk_text


async def run(ctx, deps):
    if ctx.canal == "voz":
        prompt_voz = prompts_service.render(
            "response_voice", pergunta=ctx.pergunta_reformulada, sql=ctx.sql_gerado,
            dados_amostra_json=json.dumps(ctx.amostra, ensure_ascii=False), total_linhas=ctx.total_linhas,
        )
        try:
            resp = await deps.llm.chat_texto(
                modelo=deps.cfg.model_response_voice, system=prompt_voz,
                user=ctx.pergunta_reformulada, max_tokens=400, temperatura=0.3,
            )
        except Exception as e:
            raise AnswerFailed("voz", e)
        ctx.add_usage(
            resp["tokens_input"], resp["tokens_output"],
            deps.llm.estimar_custo(deps.cfg.model_response_voice, resp["tokens_input"], resp["tokens_output"]),
        )
        texto = resp["texto"]
        ctx.resposta_texto = texto
        for ch in chunk_text(texto, 40):
            yield Token(ch)
    else:
        prompt_resp = prompts_service.render(
            "response_generator", pergunta=ctx.pergunta_reformulada, sql=ctx.sql_gerado,
            max_linhas=deps.cfg.max_linhas_amostra,
            dados_amostra_json=json.dumps(ctx.amostra, ensure_ascii=False), total_linhas=ctx.total_linhas,
        )
        try:
            resp = await deps.llm.chat_json(
                modelo=deps.cfg.model_response_text, system=prompt_resp,
                user=ctx.pergunta_reformulada, max_tokens=1500, temperatura=0.2,
            )
        except Exception as e:
            raise AnswerFailed("texto", e)
        ctx.add_usage(
            resp["tokens_input"], resp["tokens_output"],
            deps.llm.estimar_custo(deps.cfg.model_response_text, resp["tokens_input"], resp["tokens_output"]),
        )
        data_resp = resp["data"] or {}
        texto = (data_resp.get("resposta") or "").strip()
        grafico = data_resp.get("grafico_sugerido")
        spec = data_resp.get("spec_grafico")
        ctx.resposta_texto = texto
        ctx.grafico_sugerido = grafico
        ctx.spec_grafico = spec
        for ch in chunk_text(texto, 40):
            yield Token(ch)
        if grafico and spec:
            yield Chart(grafico, spec)
