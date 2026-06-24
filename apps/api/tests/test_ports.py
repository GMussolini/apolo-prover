import asyncio
from app.ports.llm import AnthropicAdapter


def test_anthropic_adapter_delega(monkeypatch):
    chamado = {}
    async def fake_chat_json(modelo, system, user, max_tokens=1500, temperatura=0.0):
        chamado["modelo"] = modelo
        return {"data": {"ok": True}, "tokens_input": 1, "tokens_output": 2}
    from app.services import anthropic_service
    monkeypatch.setattr(anthropic_service, "chat_json", fake_chat_json)

    r = asyncio.run(AnthropicAdapter().chat_json("m", "s", "u"))
    assert r["data"] == {"ok": True}
    assert chamado["modelo"] == "m"


import pandas as pd
from app.ports.sql_exec import SqlAdapter


def test_sql_adapter_delega(monkeypatch):
    async def fake_exec(base, sql, params=None, timeout=30):
        return pd.DataFrame([{"x": 1}])
    from app.core import database
    monkeypatch.setattr(database, "execute_query", fake_exec)
    df = asyncio.run(SqlAdapter().execute_query("crm", "SELECT 1"))
    assert df.iloc[0]["x"] == 1


class _FakeCur:
    def __init__(self): self.execs = []
    async def execute(self, sql, params=None): self.execs.append((sql, params))
    async def fetchone(self): return (123,)
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False


class _FakeConn:
    def __init__(self, cur): self._cur = cur
    async def cursor(self): return self._cur
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False


from contextlib import asynccontextmanager


def test_historico_turn_store_save(monkeypatch):
    cur = _FakeCur()

    @asynccontextmanager
    async def fake_hist_acquire():
        yield _FakeConn(cur)

    from app.core import database
    from app.ports import turn_store
    monkeypatch.setattr(database, "hist_acquire", fake_hist_acquire)
    monkeypatch.setattr(turn_store, "hist_acquire", fake_hist_acquire)

    from app.ports.turn_store import HistoricoTurnStore
    asyncio.run(HistoricoTurnStore().save_turn(
        sessao_id="s1", usuario_id=1, pergunta="p", pergunta_reformulada="p",
        dominio_nome="D", base_conexao="crm", confidence=0.9, canal="texto",
        resposta_texto="r", sql_gerado="SELECT 1", dados_retornados=[{"a":1}],
        grafico_sugerido=None, spec_grafico=None, tokens_input=1, tokens_output=2,
        custo_estimado=0.0, latencia_ms=10, erro=None))
    assert any("INSERT INTO tb_pergunta" in e[0] for e in cur.execs)
    assert any("INSERT INTO tb_resposta" in e[0] for e in cur.execs)
