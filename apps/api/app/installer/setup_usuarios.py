import pyodbc
from app.core.config import get_config
from app.services.auth_service import hash_senha


def seed_usuarios_iniciais() -> int:
    cfg = get_config()
    if not cfg.usuarios_iniciais:
        return 0
    criados = 0
    with pyodbc.connect(cfg.historico_conn) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            for u in cfg.usuarios_iniciais:
                cur.execute("SELECT 1 FROM tb_usuario WHERE email = ?", (u.email,))
                if cur.fetchone():
                    continue
                cur.execute("""
                    INSERT INTO tb_usuario (email, nome, senha_hash, permissoes, is_admin)
                    VALUES (?, ?, ?, ?, ?)
                """, (u.email, u.nome, hash_senha(u.senha), u.permissoes, u.is_admin))
                criados += 1
    print(f"[seed] {criados} usuários criados")
    return criados
