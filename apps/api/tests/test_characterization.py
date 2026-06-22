import json
import asyncio
from pathlib import Path
import pytest

from tests.fakes import FakeLLM, FakeSql, FakeStore, coletar_eventos

FIX = Path(__file__).parent / "fixtures" / "turns"
CASOS = sorted(p.stem for p in FIX.glob("*.json"))


def _carregar(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))


async def _rodar(caso, monkeypatch):
    from app.core import engine
    from app.pipeline import orchestrator
    from app.pipeline.stages import rate_limit as _rate_limit_stage
    from app.pipeline.deps import Deps
    from app.core.config import get_config

    fake_llm = FakeLLM(caso["llm"])
    fake_sql = FakeSql(RuntimeError(caso["sql_raise"]) if caso.get("sql_raise") else caso.get("sql_result", []))
    fake_store = FakeStore(historico=caso.get("historico", []))

    deps = Deps(llm=fake_llm, sql=fake_sql, store=fake_store, cfg=get_config())
    monkeypatch.setattr(orchestrator, "default_deps", lambda: deps)
    monkeypatch.setattr(_rate_limit_stage, "consumir_pergunta", _no_rate_limit)

    eventos = await coletar_eventos(engine.processar_pergunta(
        caso["usuario"], caso["sessao_id"], caso["pergunta"], canal=caso.get("canal", "texto"),
    ))
    return eventos


async def _no_rate_limit(uid):
    return None


def _normalizar(eventos):
    """Remove campos voláteis (latencia_ms) para o snapshot ser determinístico."""
    out = []
    for ev in eventos:
        ev = dict(ev)
        ev.pop("latencia_ms", None)
        out.append(ev)
    return out


@pytest.mark.parametrize("nome", CASOS)
def test_caracterizacao(nome, monkeypatch):
    caso = _carregar(nome)
    eventos = asyncio.run(_rodar(caso, monkeypatch))
    assert _normalizar(eventos) == caso["eventos_esperados"]
