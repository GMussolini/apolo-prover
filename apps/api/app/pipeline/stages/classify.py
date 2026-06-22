from app.domains import REGISTRY, listar_ativos
from app.services import prompts_service
from app.services import pipeline as pipe
from app.pipeline.errors import ClassifyFailed, TurnFinished
from app.pipeline.events import Token, Classification
from app.pipeline.stages._util import chunk_text


async def run(ctx, deps):
    dominios = listar_ativos()
    ctx_clf = pipe.contexto_para_classificador(dominios, ctx.pergunta)
    prompt_clf = prompts_service.render(
        "intent_classification",
        lista_dominios=ctx_clf["lista_dominios"],
        sinais_lexicais=ctx_clf["sinais_lexicais"],
        historico=ctx.historico_txt,
        pergunta=ctx.pergunta,
    )
    try:
        clf = await deps.llm.chat_json(
            modelo=deps.cfg.model_classificador, system=prompt_clf,
            user=ctx.pergunta, max_tokens=600, temperatura=0.0,
        )
    except Exception as e:
        raise ClassifyFailed(e)

    ctx.add_usage(
        clf["tokens_input"], clf["tokens_output"],
        deps.llm.estimar_custo(deps.cfg.model_classificador, clf["tokens_input"], clf["tokens_output"]),
    )

    data_clf = clf["data"] or {}
    dominio_nome = data_clf.get("dominio")
    confidence = float(data_clf.get("confidence") or 0.0)
    pergunta_reform = data_clf.get("pergunta_reformulada") or ctx.pergunta
    refinamento = data_clf.get("refinamento")

    ctx.pergunta_reformulada = pergunta_reform
    ctx.dominio_nome = dominio_nome
    ctx.confidence = round(confidence, 2)

    if not dominio_nome or confidence < 0.5 or dominio_nome not in REGISTRY:
        msg = refinamento or "Sua pergunta está muito ampla. Pode detalhar?"
        ctx.resposta_texto = msg
        for ch in chunk_text(msg, 40):
            yield Token(ch)
        raise TurnFinished

    ctx.dominio = REGISTRY[dominio_nome]
    ctx.base_conexao = ctx.dominio.base_conexao
    yield Classification(dominio_nome, round(confidence, 2))
