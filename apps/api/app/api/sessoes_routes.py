"""Histórico de sessão (F3 do PRD).

Endpoints CRUD para `tb_sessao` + leitura de `tb_pergunta` + `tb_resposta`.
Toda rota exige usuário autenticado (Depends(usuario_atual)) e checa ownership
via WHERE usuario_id = ? antes de retornar/alterar.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api._deps import usuario_atual
from app.core.database import hist_fetchall, hist_fetchone, hist_acquire

router = APIRouter(prefix="/api/sessoes", tags=["sessoes"])


# ============================================================
# Schemas
# ============================================================

class SessaoItem(BaseModel):
    id: str
    titulo: str | None = None
    canal: str
    created_at: str
    updated_at: str
    msg_count: int


class MensagemItem(BaseModel):
    id: str
    pergunta: str
    dominio: str | None = None
    confidence: float | None = None
    origem: str
    created_at: str
    resposta: str | None = None
    sql: str | None = None
    grafico_sugerido: str | None = None
    spec_grafico: dict | list | None = None


class RenomearBody(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)


# ============================================================
# Endpoints
# ============================================================

@router.get("", response_model=list[SessaoItem])
async def listar_sessoes(usuario: dict = Depends(usuario_atual)) -> list[SessaoItem]:
    """Lista as sessões do usuário logado (até 100 mais recentes, não deletadas)."""
    rows = await hist_fetchall(
        """
        SELECT TOP 100 s.id, s.titulo, s.canal, s.created_at, s.updated_at,
               COALESCE(COUNT(p.id), 0) AS msg_count
        FROM tb_sessao s
        LEFT JOIN tb_pergunta p ON p.sessao_id = s.id
        WHERE s.usuario_id = ? AND s.is_deleted = 0
        GROUP BY s.id, s.titulo, s.canal, s.created_at, s.updated_at
        ORDER BY s.updated_at DESC
        """,
        (usuario["id"],),
    )
    return [
        SessaoItem(
            id=str(r[0]),
            titulo=r[1],
            canal=r[2],
            created_at=r[3].isoformat(),
            updated_at=r[4].isoformat(),
            msg_count=int(r[5]),
        )
        for r in rows
    ]


@router.get("/{sessao_id}/mensagens", response_model=list[MensagemItem])
async def listar_mensagens(
    sessao_id: UUID,
    usuario: dict = Depends(usuario_atual),
) -> list[MensagemItem]:
    """Lista mensagens (pergunta + resposta) da sessão. Valida ownership."""
    # Checa ownership antes de devolver qualquer dado.
    owns = await hist_fetchone(
        "SELECT 1 FROM tb_sessao WHERE id = ? AND usuario_id = ? AND is_deleted = 0",
        (str(sessao_id), usuario["id"]),
    )
    if not owns:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sessão não encontrada")

    rows = await hist_fetchall(
        """
        SELECT p.id, p.pergunta, p.dominio, p.confidence_classificacao,
               p.origem, p.created_at,
               r.resposta_texto, r.sql_gerado, r.grafico_sugerido, r.spec_grafico
        FROM tb_pergunta p
        LEFT JOIN tb_resposta r ON r.pergunta_id = p.id
        WHERE p.sessao_id = ?
        ORDER BY p.created_at ASC
        """,
        (str(sessao_id),),
    )
    return [
        MensagemItem(
            id=str(r[0]),
            pergunta=r[1],
            dominio=r[2],
            confidence=float(r[3]) if r[3] is not None else None,
            origem=r[4],
            created_at=r[5].isoformat(),
            resposta=r[6],
            sql=r[7],
            grafico_sugerido=r[8],
            spec_grafico=r[9],
        )
        for r in rows
    ]


@router.patch("/{sessao_id}")
async def renomear_sessao(
    sessao_id: UUID,
    body: RenomearBody,
    usuario: dict = Depends(usuario_atual),
) -> dict:
    """Renomeia título da sessão. Valida ownership no próprio UPDATE."""
    async with hist_acquire() as conn:
        cur = await conn.cursor()
        await cur.execute(
            """
            UPDATE tb_sessao
            SET titulo = ?
            WHERE id = ? AND usuario_id = ? AND is_deleted = 0
            """,
            (body.titulo, str(sessao_id), usuario["id"]),
        )
        if cur.rowcount == 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "sessão não encontrada")
    return {"id": str(sessao_id), "titulo": body.titulo}


@router.delete("/{sessao_id}")
async def deletar_sessao(
    sessao_id: UUID,
    usuario: dict = Depends(usuario_atual),
) -> dict:
    """Soft delete da sessão (is_deleted = 1). Valida ownership no UPDATE."""
    async with hist_acquire() as conn:
        cur = await conn.cursor()
        await cur.execute(
            """
            UPDATE tb_sessao
            SET is_deleted = 1
            WHERE id = ? AND usuario_id = ? AND is_deleted = 0
            """,
            (str(sessao_id), usuario["id"]),
        )
        if cur.rowcount == 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "sessão não encontrada")
        await cur.execute(
            "INSERT INTO tb_audit (usuario_id, acao, recurso) VALUES (?, ?, ?)",
            (usuario["id"], "sessao.delete", str(sessao_id)),
        )
    return {"id": str(sessao_id), "deleted": True}
