import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from app.core.config import get_config

ALGORITMO = "HS256"


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verificar_senha(senha: str, hash_str: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), hash_str.encode("utf-8"))
    except Exception:
        return False


def criar_access_token(claims: dict, expira_em: timedelta | None = None) -> str:
    cfg = get_config()
    delta = expira_em or timedelta(minutes=cfg.jwt_access_expires_minutes)
    payload = {**claims, "exp": datetime.now(timezone.utc) + delta, "type": "access"}
    return jwt.encode(payload, cfg.jwt_secret, algorithm=ALGORITMO)


def criar_refresh_token(claims: dict) -> str:
    cfg = get_config()
    payload = {
        **claims,
        "exp": datetime.now(timezone.utc) + timedelta(days=cfg.jwt_refresh_expires_days),
        "type": "refresh",
    }
    return jwt.encode(payload, cfg.jwt_secret, algorithm=ALGORITMO)


def decodificar_token(token: str) -> dict:
    cfg = get_config()
    return jwt.decode(token, cfg.jwt_secret, algorithms=[ALGORITMO])
