import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.api._deps import usuario_atual
from app.core.engine import processar_pergunta
from app.core.rate_limiter import consumir_voz_minutos
from app.core.database import get_pg_pool
from app.services.realtime_service import criar_ephemeral_session

router = APIRouter(prefix="/api/voice", tags=["voice"])

@router.post("/session")
async def session(usuario: dict = Depends(usuario_atual)):
    try:
        data = await criar_ephemeral_session()
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"realtime indisponível: {e}")
    pool = get_pg_pool()
    sess_uuid = uuid.uuid4()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO tb_sessao (id, usuario_id, canal) VALUES (%s, %s, 'voz')",
                (str(sess_uuid), usuario["id"]),
            )
            await cur.execute(
                "INSERT INTO tb_audit (usuario_id, acao, payload) VALUES (%s, %s, %s::jsonb)",
                (usuario["id"], "voice.session.start", json.dumps({"session_id": data["session_id"]})),
            )
        await conn.commit()
    return {**data, "sessao_apolo_id": str(sess_uuid)}

class ToolCallBody(BaseModel):
    sessao_id: str
    call_id: str
    pergunta: str

@router.post("/tool-call")
async def tool_call(body: ToolCallBody, usuario: dict = Depends(usuario_atual)):
    pool = get_pg_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM tb_sessao WHERE id = %s AND usuario_id = %s",
                (body.sessao_id, usuario["id"]),
            )
            if not await cur.fetchone():
                raise HTTPException(status.HTTP_404_NOT_FOUND, "sessao nao encontrada")

    resposta_final = ""
    async for evt in processar_pergunta(usuario, body.sessao_id, body.pergunta, canal="voz"):
        if evt.get("type") == "token":
            resposta_final += evt["delta"]
        if evt.get("type") == "done":
            break

    return {"call_id": body.call_id, "output": resposta_final or "Não consegui processar agora."}

class VozMinutosBody(BaseModel):
    minutos: float

@router.post("/consumo")
async def registrar_consumo(body: VozMinutosBody, usuario: dict = Depends(usuario_atual)):
    await consumir_voz_minutos(usuario["id"], body.minutos)
    return {"ok": True}
