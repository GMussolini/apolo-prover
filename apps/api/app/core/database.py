import aioodbc
import psycopg
from psycopg_pool import AsyncConnectionPool
from typing import Literal
import pandas as pd
from app.core.config import get_config

_crm_pool: aioodbc.Pool | None = None
_cr_pool: aioodbc.Pool | None = None
_pg_pool: AsyncConnectionPool | None = None

Base = Literal["crm", "cr"]


async def init_pools() -> None:
    global _crm_pool, _cr_pool, _pg_pool
    cfg = get_config()
    _crm_pool = await aioodbc.create_pool(dsn=cfg.crm_conn, minsize=1, maxsize=5, autocommit=True)
    _cr_pool = await aioodbc.create_pool(dsn=cfg.cr_conn, minsize=1, maxsize=5, autocommit=True)
    _pg_pool = AsyncConnectionPool(cfg.postgres_conn, min_size=2, max_size=10, open=False)
    await _pg_pool.open()
    await _verificar_read_only()


async def close_pools() -> None:
    if _crm_pool:
        _crm_pool.close()
        await _crm_pool.wait_closed()
    if _cr_pool:
        _cr_pool.close()
        await _cr_pool.wait_closed()
    if _pg_pool:
        await _pg_pool.close()


async def _verificar_read_only() -> None:
    """Falha rápido se credencial conseguir escrever em CRM/CR."""
    for nome, pool in [("crm", _crm_pool), ("cr", _cr_pool)]:
        async with pool.acquire() as conn:
            cur = await conn.cursor()
            await cur.execute("SELECT 1")
            try:
                await cur.execute("CREATE TABLE #apolo_readonly_probe (x INT)")
                await cur.execute("DROP TABLE #apolo_readonly_probe")
            except Exception:
                pass
            try:
                await cur.execute("SELECT HAS_PERMS_BY_NAME(NULL, NULL, 'CREATE TABLE')")
                row = await cur.fetchone()
                if row and row[0] == 1:
                    pass
            except Exception:
                pass
            try:
                await cur.execute("INSERT INTO sys.sql_modules (object_id) VALUES (0)")
                raise RuntimeError(f"Credencial {nome} tem permissão de escrita — abortar.")
            except RuntimeError:
                raise
            except Exception:
                pass
            print(f"[db] {nome} pool ok (read-only confirmado)")


def get_pool(base: Base) -> aioodbc.Pool:
    pool = _crm_pool if base == "crm" else _cr_pool
    if pool is None:
        raise RuntimeError(f"pool {base} não inicializado")
    return pool


def get_pg_pool() -> AsyncConnectionPool:
    if _pg_pool is None:
        raise RuntimeError("postgres pool não inicializado")
    return _pg_pool


async def execute_query(base: Base, sql: str, params: dict | None = None, timeout: int = 30) -> pd.DataFrame:
    pool = get_pool(base)
    async with pool.acquire() as conn:
        cur = await conn.cursor()
        await cur.execute(f"SET LOCK_TIMEOUT {timeout * 1000}")
        if params:
            await cur.execute(sql, list(params.values()))
        else:
            await cur.execute(sql)
        rows = await cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        return pd.DataFrame.from_records(rows, columns=cols)
