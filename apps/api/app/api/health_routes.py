import time
from fastapi import APIRouter
from app.core.database import get_pool, hist_fetchone

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
        await hist_fetchone("SELECT 1")
        status["historico"] = {"ok": True, "latencia_ms": int((time.perf_counter() - start) * 1000)}
    except Exception as e:
        status["historico"] = {"ok": False, "erro": str(e)[:200]}
        status["status"] = "down"
    return status
