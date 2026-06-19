import httpx
from app.core.config import get_config
from app.services.prompts_service import carregar

def build_tools() -> list[dict]:
    return [{
        "type": "function",
        "name": "consultar_apolo",
        "description": (
            "Consulta dados do CRM (vendas, leads, clientes, tarefas, reuniões, Coordenador IA) "
            "ou do Controle de Recursos (financeiro, folha, projetos, alocação) da Prover Tecnologia. "
            "Use SEMPRE para qualquer pergunta sobre dados, números, nomes, datas, valores. NUNCA invente."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pergunta": {
                    "type": "string",
                    "description": "A pergunta do usuário em PT-BR, completa e auto-contida.",
                },
            },
            "required": ["pergunta"],
        },
    }]

async def criar_ephemeral_session() -> dict:
    """Cria sessão Realtime efêmera via REST direto (independe da versão do SDK openai)."""
    cfg = get_config()
    payload = {
        "session": {
            "type": "realtime",
            "model": cfg.model_realtime_voice,
            "instructions": carregar("voice_system"),
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": 24000},
                    "turn_detection": {"type": "server_vad", "silence_duration_ms": 500},
                    "transcription": {"model": "gpt-4o-transcribe"},
                },
                "output": {
                    "format": {"type": "audio/pcm", "rate": 24000},
                    "voice": cfg.voice_default,
                },
            },
            "tools": build_tools(),
        }
    }
    async with httpx.AsyncClient(timeout=20) as cli:
        resp = await cli.post(
            "https://api.openai.com/v1/realtime/client_secrets",
            headers={
                "Authorization": f"Bearer {cfg.openai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"OpenAI realtime {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    cs = data.get("client_secret") or {}
    # GA pode retornar o token no top-level ("value") ou aninhado em client_secret
    token = data.get("value") or cs.get("value") or cs.get("id")
    expires = data.get("expires_at") or cs.get("expires_at")
    return {
        "ephemeral_token": token,
        "expires_at": expires,
        "model": cfg.model_realtime_voice,
        "session_id": (data.get("session") or {}).get("id"),
    }
