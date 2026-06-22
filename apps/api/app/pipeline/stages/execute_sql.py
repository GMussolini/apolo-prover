import json
import pandas as pd
from app.pipeline.errors import SqlExecFailed
from app.pipeline.events import Status


def _df_para_amostra(df, max_linhas):
    total = len(df)
    if total == 0:
        return [], 0
    amostra = df.head(max_linhas).copy()
    for c in amostra.columns:
        if pd.api.types.is_datetime64_any_dtype(amostra[c]):
            amostra[c] = amostra[c].astype(str)
    return json.loads(amostra.to_json(orient="records", date_format="iso", default_handler=str)), total


async def run(ctx, deps):
    yield Status("Consultando dados...")
    try:
        df = await deps.sql.execute_query(
            ctx.dominio.base_conexao, ctx.sql_gerado, timeout=deps.cfg.sql_query_timeout_seconds,
        )
    except Exception as e:
        raise SqlExecFailed(e)
    amostra, total_linhas = _df_para_amostra(df, deps.cfg.max_linhas_amostra)
    ctx.amostra = amostra
    ctx.total_linhas = total_linhas
    ctx.dados_retornados = amostra[: deps.cfg.max_linhas_dados_retornados]
    yield Status("Montando resposta...")
