from datetime import datetime, timezone
from typing import Literal
from fastapi import HTTPException, status
from app.core.config import get_config
from app.core.database import get_pg_pool

Bucket = Literal["minuto", "hora", "dia"]

def janela_truncada(dt: datetime, bucket: Bucket) -> datetime:
    if bucket == "minuto":
        return dt.replace(second=0, microsecond=0)
    if bucket == "hora":
        return dt.replace(minute=0, second=0, microsecond=0)
    if bucket == "dia":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(bucket)

async def consumir_pergunta(usuario_id: int) -> None:
    cfg = get_config()
    agora = datetime.now(timezone.utc)
    pool = get_pg_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            for bucket, limite in [
                ("minuto", cfg.rate_limit_perguntas_por_minuto),
                ("dia",    cfg.rate_limit_perguntas_por_dia),
            ]:
                janela = janela_truncada(agora, bucket)
                await cur.execute("""
                    INSERT INTO tb_rate_limit (usuario_id, bucket, janela_inicio, contagem)
                    VALUES (%s, %s, %s, 1)
                    ON CONFLICT (usuario_id, bucket, janela_inicio)
                    DO UPDATE SET contagem = tb_rate_limit.contagem + 1
                    RETURNING contagem
                """, (usuario_id, bucket, janela))
                contagem = (await cur.fetchone())[0]
                if contagem > limite:
                    raise HTTPException(
                        status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"rate limit {bucket}: {contagem}/{limite}",
                        headers={"Retry-After": "60" if bucket == "minuto" else "3600"},
                    )
        await conn.commit()

async def consumir_voz_minutos(usuario_id: int, minutos: float) -> None:
    cfg = get_config()
    agora = datetime.now(timezone.utc)
    janela = janela_truncada(agora, "dia")
    pool = get_pg_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO tb_rate_limit (usuario_id, bucket, janela_inicio, contagem)
                VALUES (%s, 'voz_min', %s, %s)
                ON CONFLICT (usuario_id, bucket, janela_inicio)
                DO UPDATE SET contagem = tb_rate_limit.contagem + EXCLUDED.contagem
                RETURNING contagem
            """, (usuario_id, janela, int(minutos * 100)))
            total_centesimo_min = (await cur.fetchone())[0]
            if total_centesimo_min / 100 > cfg.rate_limit_voz_minutos_por_dia:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"limite voz diário ({cfg.rate_limit_voz_minutos_por_dia} min) atingido",
                )
        await conn.commit()
