from app.pipeline import sql_builder
from app.core.sql_guard import SqlNaoPermitidoError
from app.pipeline.errors import SqlBlocked, SqlBuildFailed
from app.pipeline.events import Sql


async def run(ctx, deps):
    try:
        sql_final = sql_builder.montar_sql_final(ctx.dominio, ctx.partes)
    except SqlNaoPermitidoError as e:
        raise SqlBlocked(e)
    except Exception as e:
        raise SqlBuildFailed(e)
    ctx.sql_gerado = sql_final
    yield Sql(sql_final)
