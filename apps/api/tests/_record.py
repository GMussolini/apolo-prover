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
from app.services import anthropic_service
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
    with patch.object(anthropic_service, "chat_json", fake_llm.chat_json), \
         patch.object(anthropic_service, "chat_texto", fake_llm.chat_texto), \
         patch.object(anthropic_service, "estimar_custo", fake_llm.estimar_custo), \
         patch.object(engine, "execute_query", fake_sql.execute_query), \
         patch.object(engine, "_carregar_historico", fake_store.load_history), \
         patch.object(engine, "_salvar_pergunta_resposta", lambda **kw: fake_store.save_turn(**kw)), \
         patch.object(engine, "consumir_pergunta", _no_rate_limit):
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
