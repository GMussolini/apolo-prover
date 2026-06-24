import base64
import json
import os
from functools import lru_cache
from pathlib import Path
from pydantic import BaseModel


class UsuarioInicial(BaseModel):
    email: str
    nome: str
    senha: str
    permissoes: str = ""
    is_admin: bool = False


class Config(BaseModel):
    jwt_secret: str
    jwt_access_expires_minutes: int = 60
    jwt_refresh_expires_days: int = 7

    anthropic_api_key: str
    openai_api_key: str

    model_classificador: str = "claude-sonnet-4-6"
    model_sql_generator: str = "claude-sonnet-4-6"
    model_response_text: str = "claude-haiku-4-5"
    model_response_voice: str = "claude-haiku-4-5"
    model_realtime_voice: str = "gpt-realtime"
    voice_default: str = "ash"

    crm_conn: str
    cr_conn: str
    historico_conn: str

    cors_origins: list[str] = ["http://localhost:3000"]

    rate_limit_perguntas_por_minuto: int = 60
    rate_limit_perguntas_por_dia: int = 1000
    rate_limit_voz_minutos_por_dia: int = 30
    rate_limit_logins_por_hora_por_ip: int = 10
    voz_timeout_sessao_minutos: int = 10

    sql_query_timeout_seconds: int = 30
    max_linhas_amostra: int = 100
    max_linhas_dados_retornados: int = 500

    usuarios_iniciais: list[UsuarioInicial] = []


@lru_cache
def get_config() -> Config:
    # Em produção (Azure Container Apps) injetamos a config inteira via secret
    # na env APOLO_CONFIG_JSON — sem arquivo no image. Localmente lê config.json.
    raw = os.environ.get("APOLO_CONFIG_JSON")
    if not raw and os.environ.get("APOLO_CONFIG_B64"):
        raw = base64.b64decode(os.environ["APOLO_CONFIG_B64"]).decode("utf-8")
    if raw:
        return Config(**json.loads(raw))
    path = Path(os.environ.get("APOLO_CONFIG", "config.json"))
    if not path.exists():
        raise RuntimeError(f"config.json não encontrado em {path.resolve()}")
    return Config(**json.loads(path.read_text(encoding="utf-8")))
