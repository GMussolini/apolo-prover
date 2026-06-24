"""POST /api/chat — endpoint SSE de chat texto (F6 do PRD).

Recebe pergunta, cria sessão se necessário, e streama eventos do engine
(status, classification, sql, token, chart, done) em formato Server-Sent Events.
"""
import json
import uuid
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, Field

from app.api._deps import usuario_atual
from app.core.engine import processar_pergunta
from app.core.database import hist_execute

router = APIRouter(prefix="/api", tags=["chat"])


class ChatBody(BaseModel):
    sessao_id: str | None = None
    pergunta: str = Field(min_length=1, max_length=2000)


@router.post("/chat")
async def chat(body: ChatBody, request: Request, usuario: dict = Depends(usuario_atual)):
    sessao_id = body.sessao_id

    if not sessao_id:
        novo_id = uuid.uuid4()
        await hist_execute(
            "INSERT INTO tb_sessao (id, usuario_id, canal) VALUES (?, ?, 'texto')",
            (str(novo_id), usuario["id"]),
        )
        sessao_id = str(novo_id)

    async def gerar():
        yield {"event": "session", "data": json.dumps({"sessao_id": sessao_id})}
        try:
            async for evt in processar_pergunta(usuario, sessao_id, body.pergunta, canal="texto"):
                if await request.is_disconnected():
                    break
                yield {"event": "message", "data": json.dumps(evt, default=str, ensure_ascii=False)}
        except Exception as e:
            yield {
                "event": "message",
                "data": json.dumps({"type": "error", "message": str(e)[:300]}, ensure_ascii=False),
            }

    return EventSourceResponse(gerar())
