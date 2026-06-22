from fastapi import HTTPException
from app.core.rate_limiter import consumir_pergunta
from app.pipeline.errors import RateLimited
from app.pipeline.events import Status


async def run(ctx, deps):
    try:
        await consumir_pergunta(ctx.usuario["id"])
    except HTTPException as e:
        raise RateLimited(e.detail)
    yield Status("Entendendo sua pergunta...")
