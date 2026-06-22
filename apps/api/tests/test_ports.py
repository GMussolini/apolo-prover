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
