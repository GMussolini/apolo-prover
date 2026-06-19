import json
from anthropic import AsyncAnthropic
from app.core.config import get_config
from app.core.logging_config import logger

_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        cfg = get_config()
        _client = AsyncAnthropic(api_key=cfg.anthropic_api_key)
    return _client


async def chat_json(modelo: str, system: str, user: str, max_tokens: int = 1500, temperatura: float = 0.0) -> dict:
    """Chama Claude e forca resposta JSON parseada."""
    client = get_client()
    resp = await client.messages.create(
        model=modelo,
        max_tokens=max_tokens,
        temperature=temperatura,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    texto = "".join(b.text for b in resp.content if b.type == "text")
    try:
        # Tenta extrair JSON entre ```json ... ``` se vier embrulhado
        if "```json" in texto:
            texto = texto.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in texto:
            texto = texto.split("```", 1)[1].split("```", 1)[0]
        return {
            "data": json.loads(texto.strip()),
            "tokens_input": resp.usage.input_tokens,
            "tokens_output": resp.usage.output_tokens,
        }
    except json.JSONDecodeError as e:
        logger.error("anthropic.json_parse_failed", erro=str(e), texto_raw=texto[:500])
        raise


async def chat_texto(modelo: str, system: str, user: str, max_tokens: int = 500, temperatura: float = 0.3) -> dict:
    """Chama Claude e retorna texto puro (sem JSON)."""
    client = get_client()
    resp = await client.messages.create(
        model=modelo,
        max_tokens=max_tokens,
        temperature=temperatura,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    texto = "".join(b.text for b in resp.content if b.type == "text")
    return {
        "texto": texto.strip(),
        "tokens_input": resp.usage.input_tokens,
        "tokens_output": resp.usage.output_tokens,
    }


def estimar_custo(modelo: str, tokens_input: int, tokens_output: int) -> float:
    """USD. Atualizar quando precos mudarem."""
    precos_per_1m = {
        "claude-sonnet-4-6":  (3.0,  15.0),
        "claude-haiku-4-5":   (0.8,  4.0),
    }
    pin, pout = precos_per_1m.get(modelo, (5.0, 20.0))
    return (tokens_input * pin + tokens_output * pout) / 1_000_000
