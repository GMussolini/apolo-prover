"""Smoke test contra CRM real — requer config.json válida + acesso à rede prod.

Marcado com skip por default: o test runner não tem credenciais nem rota até o SQL Server.
Pra rodar localmente: APOLO_CONFIG=config.json APOLO_RUN_DB_SMOKE=1 pytest tests/test_database.py
"""
import os
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("APOLO_RUN_DB_SMOKE") != "1",
    reason="smoke contra DB real desligado (set APOLO_RUN_DB_SMOKE=1 pra rodar)",
)


@pytest.mark.asyncio
async def test_crm_pool_responde():
    from app.core.database import init_pools, close_pools, execute_query

    await init_pools()
    try:
        df = await execute_query("crm", "SELECT TOP 1 Id, Nome FROM PreLeads ORDER BY Id DESC")
        assert len(df.columns) == 2
        assert len(df) <= 1
    finally:
        await close_pools()


@pytest.mark.asyncio
async def test_cr_pool_responde():
    from app.core.database import init_pools, close_pools, execute_query

    await init_pools()
    try:
        df = await execute_query("cr", "SELECT TOP 1 1 AS um")
        assert len(df) <= 1
    finally:
        await close_pools()
