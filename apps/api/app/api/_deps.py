from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth_service import decodificar_token
from app.core.database import hist_fetchone

bearer = HTTPBearer(auto_error=False)


async def usuario_atual(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token ausente")
    try:
        payload = decodificar_token(cred.credentials)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token inválido")
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token errado (use access)")
    row = await hist_fetchone(
        "SELECT id, email, nome, permissoes, is_admin, ativo FROM tb_usuario WHERE id = ?",
        (int(payload["sub"]),),
    )
    if not row or not row[5]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "usuário inativo ou inexistente")
    return {"id": row[0], "email": row[1], "nome": row[2], "permissoes": row[3], "is_admin": row[4]}


async def admin_atual(usuario: dict = Depends(usuario_atual)) -> dict:
    if not usuario["is_admin"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin required")
    return usuario
