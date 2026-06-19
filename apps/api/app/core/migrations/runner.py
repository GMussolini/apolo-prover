import psycopg
from pathlib import Path
from app.core.config import get_config

MIGRATIONS_DIR = Path(__file__).parent / "sql"


def aplicar_migrations() -> int:
    cfg = get_config()
    aplicadas = 0
    with psycopg.connect(cfg.postgres_conn) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tb_schema_version (
                    arquivo VARCHAR(200) PRIMARY KEY,
                    aplicado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
                cur.execute("SELECT 1 FROM tb_schema_version WHERE arquivo = %s", (sql_file.name,))
                if cur.fetchone():
                    continue
                print(f"[migration] aplicando {sql_file.name}")
                cur.execute(sql_file.read_text(encoding="utf-8"))
                cur.execute("INSERT INTO tb_schema_version (arquivo) VALUES (%s)", (sql_file.name,))
                aplicadas += 1
        conn.commit()
    print(f"[migration] {aplicadas} aplicadas")
    return aplicadas
