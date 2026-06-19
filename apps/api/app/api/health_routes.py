import time
from fastapi import APIRouter
from app.core.database import get_pool, get_pg_pool

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    status = {"status": "ok"}
    for base in ("crm", "cr"):
        try:
            start = time.perf_counter()
            pool = get_pool(base)
            async with pool.acquire() as conn:
                cur = await conn.cursor()
                await cur.execute("SELECT 1")
                await cur.fetchone()
            status[base] = {"ok": True, "latencia_ms": int((time.perf_counter() - start) * 1000)}
        except Exception as e:
            status[base] = {"ok": False, "erro": str(e)[:200]}
            status["status"] = "degraded"
    try:
        start = time.perf_counter()
        pool = get_pg_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                await cur.fetchone()
        status["postgres"] = {"ok": True, "latencia_ms": int((time.perf_counter() - start) * 1000)}
    except Exception as e:
        status["postgres"] = {"ok": False, "erro": str(e)[:200]}
        status["status"] = "down"
    return status
