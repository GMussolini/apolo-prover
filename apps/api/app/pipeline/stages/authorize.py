from app.core.permissoes import usuario_pode
from app.pipeline.errors import TurnFinished
from app.pipeline.events import Token, Status
from app.pipeline.stages._util import chunk_text


async def run(ctx, deps):
    if not usuario_pode(
        ctx.usuario.get("permissoes", "") or "",
        ctx.dominio.permissoes_necessarias,
        ctx.usuario.get("is_admin", False),
    ):
        msg = (
            f"Você não tem permissão para acessar o domínio **{ctx.dominio_nome}**. "
            "Fale com o administrador se precisar de acesso."
        )
        ctx.resposta_texto = msg
        ctx.erro = "permissao_negada"
        for ch in chunk_text(msg, 40):
            yield Token(ch)
        raise TurnFinished
    yield Status("Gerando consulta...")
