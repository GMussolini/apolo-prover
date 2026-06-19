import psycopg
from app.core.config import get_config
from app.services.auth_service import hash_senha


def seed_usuarios_iniciais() -> int:
    cfg = get_config()
    if not cfg.usuarios_iniciais:
        return 0
    criados = 0
    with psycopg.connect(cfg.postgres_conn) as conn:
        with conn.cursor() as cur:
            for u in cfg.usuarios_iniciais:
                cur.execute("SELECT 1 FROM tb_usuario WHERE email = %s", (u.email,))
                if cur.fetchone():
                    continue
                cur.execute("""
                    INSERT INTO tb_usuario (email, nome, senha_hash, permissoes, is_admin)
                    VALUES (%s, %s, %s, %s, %s)
                """, (u.email, u.nome, hash_senha(u.senha), u.permissoes, u.is_admin))
                criados += 1
        conn.commit()
    print(f"[seed] {criados} usuários criados")
    return criados
