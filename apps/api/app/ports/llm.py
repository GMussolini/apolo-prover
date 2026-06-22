from typing import Protocol
from app.services import anthropic_service


class LLMPort(Protocol):
    async def chat_json(self, modelo: str, system: str, user: str,
                        max_tokens: int = 1500, temperatura: float = 0.0) -> dict: ...
    async def chat_texto(self, modelo: str, system: str, user: str,
                         max_tokens: int = 500, temperatura: float = 0.3) -> dict: ...
    def estimar_custo(self, modelo: str, ti: int, to: int) -> float: ...


class AnthropicAdapter:
    async def chat_json(self, modelo, system, user, max_tokens=1500, temperatura=0.0) -> dict:
        return await anthropic_service.chat_json(modelo, system, user, max_tokens, temperatura)

    async def chat_texto(self, modelo, system, user, max_tokens=500, temperatura=0.3) -> dict:
        return await anthropic_service.chat_texto(modelo, system, user, max_tokens, temperatura)

    def estimar_custo(self, modelo, ti, to) -> float:
        return anthropic_service.estimar_custo(modelo, ti, to)
