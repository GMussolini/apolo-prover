import os
import json

# Configuração mínima — deve ser injetada ANTES de qualquer import do app
if not os.environ.get("APOLO_CONFIG_JSON") and not os.environ.get("APOLO_CONFIG_B64"):
    os.environ["APOLO_CONFIG_JSON"] = json.dumps({
        "jwt_secret": "x", "anthropic_api_key": "x", "openai_api_key": "x",
        "crm_conn": "x", "cr_conn": "x", "postgres_conn": "x",
    })

import asyncio
from pathlib import Path
from unittest.mock import patch
from app.core import engine
from app.pipeline import orchestrator
from app.pipeline.stages import rate_limit as _rate_limit_stage
from app.pipeline.deps import Deps
from app.core.config import get_config
from tests.fakes import FakeLLM, FakeSql, FakeStore, coletar_eventos

FIX = Path(__file__).parent / "fixtures" / "turns"


def _normalizar(eventos):
    out = []
    for ev in eventos:
        ev = dict(ev)
        ev.pop("latencia_ms", None)
        out.append(ev)
    return out


async def _no_rate_limit(uid):
    return None


async def _rodar(caso):
    fake_llm = FakeLLM(caso["llm"])
    fake_sql = FakeSql(RuntimeError(caso["sql_raise"]) if caso.get("sql_raise") else caso.get("sql_result", []))
    fake_store = FakeStore(historico=caso.get("historico", []))
    deps = Deps(llm=fake_llm, sql=fake_sql, store=fake_store, cfg=get_config())
    with patch.object(orchestrator, "default_deps", lambda: deps), \
         patch.object(_rate_limit_stage, "consumir_pergunta", _no_rate_limit):
        return await coletar_eventos(engine.processar_pergunta(
            caso["usuario"], caso["sessao_id"], caso["pergunta"], canal=caso.get("canal", "texto")))


def main():
    for p in sorted(FIX.glob("*.json")):
        caso = json.loads(p.read_text(encoding="utf-8"))
        eventos = asyncio.run(_rodar(caso))
        caso["eventos_esperados"] = _normalizar(eventos)
        p.write_text(json.dumps(caso, ensure_ascii=False, indent=2), encoding="utf-8")
        print("gravado", p.stem, "->", len(caso["eventos_esperados"]), "eventos")


if __name__ == "__main__":
    main()
