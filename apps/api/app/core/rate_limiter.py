from datetime import datetime, timezone
from typing import Literal
from fastapi import HTTPException, status
from app.core.config import get_config
from app.core.database import hist_acquire

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
    async with hist_acquire() as conn:
        cur = await conn.cursor()
        for bucket, limite in [
            ("minuto", cfg.rate_limit_perguntas_por_minuto),
            ("dia",    cfg.rate_limit_perguntas_por_dia),
        ]:
            janela = janela_truncada(agora, bucket)
            # MERGE faz upsert (ON CONFLICT do Postgres → MERGE no T-SQL)
            await cur.execute("""
                MERGE tb_rate_limit AS t
                USING (SELECT ? AS usuario_id, ? AS bucket, ? AS janela_inicio) AS s
                  ON t.usuario_id=s.usuario_id AND t.bucket=s.bucket AND t.janela_inicio=s.janela_inicio
                WHEN MATCHED THEN UPDATE SET contagem = t.contagem + 1
                WHEN NOT MATCHED THEN INSERT (usuario_id, bucket, janela_inicio, contagem)
                     VALUES (s.usuario_id, s.bucket, s.janela_inicio, 1);
            """, (usuario_id, bucket, janela))
            # Após o MERGE, selecionar a contagem atual na mesma conexão
            await cur.execute(
                "SELECT contagem FROM tb_rate_limit WHERE usuario_id=? AND bucket=? AND janela_inicio=?",
                (usuario_id, bucket, janela),
            )
            result = await cur.fetchone()
            contagem = result[0] if result else 1
            if contagem > limite:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"rate limit {bucket}: {contagem}/{limite}",
                    headers={"Retry-After": "60" if bucket == "minuto" else "3600"},
                )

async def consumir_voz_minutos(usuario_id: int, minutos: float) -> None:
    cfg = get_config()
    agora = datetime.now(timezone.utc)
    janela = janela_truncada(agora, "dia")
    incremento = int(minutos * 100)
    async with hist_acquire() as conn:
        cur = await conn.cursor()
        await cur.execute("""
            MERGE tb_rate_limit AS t
            USING (SELECT ? AS usuario_id, 'voz_min' AS bucket, ? AS janela_inicio) AS s
              ON t.usuario_id=s.usuario_id AND t.bucket=s.bucket AND t.janela_inicio=s.janela_inicio
            WHEN MATCHED THEN UPDATE SET contagem = t.contagem + ?
            WHEN NOT MATCHED THEN INSERT (usuario_id, bucket, janela_inicio, contagem)
                 VALUES (s.usuario_id, s.bucket, s.janela_inicio, ?);
        """, (usuario_id, janela, incremento, incremento))
        await cur.execute(
            "SELECT contagem FROM tb_rate_limit WHERE usuario_id=? AND bucket='voz_min' AND janela_inicio=?",
            (usuario_id, janela),
        )
        result = await cur.fetchone()
        total_centesimo_min = result[0] if result else incremento
        if total_centesimo_min / 100 > cfg.rate_limit_voz_minutos_por_dia:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"limite voz diário ({cfg.rate_limit_voz_minutos_por_dia} min) atingido",
            )
