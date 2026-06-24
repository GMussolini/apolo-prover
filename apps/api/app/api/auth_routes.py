from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from app.services.auth_service import verificar_senha, criar_access_token, criar_refresh_token, decodificar_token
from app.core.database import hist_fetchone, hist_acquire

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: EmailStr
    senha: str


class TokenResp(BaseModel):
    access_token: str
    refresh_token: str
    usuario: dict


@router.post("/login", response_model=TokenResp)
async def login(body: LoginBody, request: Request):
    row = await hist_fetchone(
        "SELECT id, nome, senha_hash, permissoes, is_admin, ativo FROM tb_usuario WHERE email = ?",
        (body.email,),
    )
    if not row or not row[5] or not verificar_senha(body.senha, row[2]):
        async with hist_acquire() as conn:
            cur = await conn.cursor()
            await cur.execute(
                "INSERT INTO tb_audit (acao, recurso, payload, ip) VALUES (?, ?, ?, ?)",
                ("login.fail", body.email, '{}', request.client.host if request.client else None),
            )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "credenciais inválidas")
    async with hist_acquire() as conn:
        cur = await conn.cursor()
        await cur.execute(
            "UPDATE tb_usuario SET ultimo_login = SYSUTCDATETIME() WHERE id = ?",
            (row[0],),
        )
        await cur.execute(
            "INSERT INTO tb_audit (usuario_id, acao, ip) VALUES (?, ?, ?)",
            (row[0], "login.ok", request.client.host if request.client else None),
        )
    claims = {"sub": str(row[0]), "permissoes": row[3], "is_admin": row[4]}
    return TokenResp(
        access_token=criar_access_token(claims),
        refresh_token=criar_refresh_token({"sub": str(row[0])}),
        usuario={"id": row[0], "email": body.email, "nome": row[1], "permissoes": row[3], "is_admin": row[4]},
    )


class RefreshBody(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=TokenResp)
async def refresh(body: RefreshBody):
    try:
        payload = decodificar_token(body.refresh_token)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh inválido")
    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token errado")
    row = await hist_fetchone(
        "SELECT id, email, nome, permissoes, is_admin, ativo FROM tb_usuario WHERE id = ?",
        (int(payload["sub"]),),
    )
    if not row or not row[5]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "usuário inativo")
    claims = {"sub": str(row[0]), "permissoes": row[3], "is_admin": row[4]}
    return TokenResp(
        access_token=criar_access_token(claims),
        refresh_token=criar_refresh_token({"sub": str(row[0])}),
        usuario={"id": row[0], "email": row[1], "nome": row[2], "permissoes": row[3], "is_admin": row[4]},
    )
