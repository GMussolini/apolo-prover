import aioodbc
from contextlib import asynccontextmanager
from typing import Literal
import pandas as pd
from app.core.config import get_config

_crm_pool: aioodbc.Pool | None = None
_cr_pool: aioodbc.Pool | None = None
_hist_pool: aioodbc.Pool | None = None

Base = Literal["crm", "cr"]


async def init_pools() -> None:
    global _crm_pool, _cr_pool, _hist_pool
    cfg = get_config()
    _crm_pool = await aioodbc.create_pool(dsn=cfg.crm_conn, minsize=1, maxsize=5, autocommit=True)
    _cr_pool = await aioodbc.create_pool(dsn=cfg.cr_conn, minsize=1, maxsize=5, autocommit=True)
    # Historico (SQL Server). autocommit=True: cada statement confirma sozinho — simples e
    # suficiente para log de conversas/auditoria (nao e dado transacional critico).
    _hist_pool = await aioodbc.create_pool(dsn=cfg.historico_conn, minsize=2, maxsize=10, autocommit=True)
    await _verificar_read_only()


async def close_pools() -> None:
    for pool in (_crm_pool, _cr_pool, _hist_pool):
        if pool:
            pool.close()
            await pool.wait_closed()


async def _verificar_read_only() -> None:
    """Falha rapido se a credencial conseguir escrever em CRM/CR (essas bases sao SO leitura)."""
    for nome, pool in [("crm", _crm_pool), ("cr", _cr_pool)]:
        async with pool.acquire() as conn:
            cur = await conn.cursor()
            await cur.execute("SELECT 1")
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


def get_hist_pool() -> aioodbc.Pool:
    if _hist_pool is None:
        raise RuntimeError("pool historico não inicializado")
    return _hist_pool


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


# ============================================================
# Helpers do historico (SQL Server). Usam '?' como placeholder.
# ============================================================

@asynccontextmanager
async def hist_acquire():
    """Conexao do pool de historico para operacoes multi-statement / transacionais."""
    pool = get_hist_pool()
    async with pool.acquire() as conn:
        yield conn


async def hist_fetchall(sql: str, params: tuple = ()) -> list:
    async with hist_acquire() as conn:
        cur = await conn.cursor()
        await cur.execute(sql, params)
        return await cur.fetchall()


async def hist_fetchone(sql: str, params: tuple = ()):
    async with hist_acquire() as conn:
        cur = await conn.cursor()
        await cur.execute(sql, params)
        return await cur.fetchone()


async def hist_execute(sql: str, params: tuple = ()) -> int:
    """Executa um statement e retorna rowcount."""
    async with hist_acquire() as conn:
        cur = await conn.cursor()
        await cur.execute(sql, params)
        return cur.rowcount
