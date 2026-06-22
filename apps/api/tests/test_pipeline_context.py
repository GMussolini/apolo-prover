import time
from app.pipeline.context import TurnContext

def test_add_usage_e_save_kwargs():
    ctx = TurnContext(usuario={"id": 7}, sessao_id="s", pergunta="p", canal="texto", t0=time.perf_counter())
    ctx.add_usage(10, 5, 0.001)
    ctx.add_usage(20, 3, 0.002)
    assert ctx.tokens_input == 30 and ctx.tokens_output == 8
    assert round(ctx.custo, 3) == 0.003
    ctx.dominio_nome = "CRM_PIPELINE"
    kw = ctx.save_kwargs()
    assert kw["usuario_id"] == 7
    assert kw["dominio_nome"] == "CRM_PIPELINE"
    assert kw["tokens_input"] == 30 and kw["tokens_output"] == 8
    assert "latencia_ms" in kw
