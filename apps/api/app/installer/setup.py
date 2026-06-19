"""Installer/bootstrap helpers do APOLO_PROVER.

Roda uma vez antes do primeiro `docker compose up`, ou no entrypoint do container,
pra garantir que o `config.json` esteja com segredos reais (não os placeholders
`GERAR_*` que vêm do `config.example.json`).
"""
import json
import os
import secrets
from pathlib import Path


def garantir_secret_jwt() -> bool:
    """Se `config.json.jwt_secret` começa com 'GERAR_', substitui por um token
    aleatório de 64 chars (url-safe) e regrava o arquivo.

    Retorna True se rotacionou o secret, False se já estava OK.
    """
    path = Path(os.environ.get("APOLO_CONFIG", "config.json"))
    if not path.exists():
        print(f"[setup] config.json não encontrado em {path.resolve()} — pulando")
        return False

    cfg = json.loads(path.read_text(encoding="utf-8"))
    secret_atual = cfg.get("jwt_secret", "")

    if not secret_atual.startswith("GERAR_"):
        return False

    cfg["jwt_secret"] = secrets.token_urlsafe(64)
    path.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("[setup] JWT secret gerado (64 chars url-safe)")
    return True


def main() -> None:
    """Entrypoint manual: `python -m app.installer.setup`."""
    garantir_secret_jwt()


if __name__ == "__main__":
    main()
