import re
import pyodbc
from pathlib import Path
from app.core.config import get_config

MIGRATIONS_DIR = Path(__file__).parent / "sql"


def _batches(sql_text: str) -> list[str]:
    """Divide o script T-SQL em batches separados por linhas contendo só 'GO'."""
    parts = re.split(r"(?im)^[ \t]*GO[ \t]*$", sql_text)
    return [b.strip() for b in parts if b.strip()]


def _garantir_database(conn_str: str) -> None:
    """Cria o database alvo se ele não existir (dev/local). Em Azure SQL o banco já
    vem provisionado — aí isto vira no-op ou falha sem permissão e seguimos."""
    m = re.search(r"Database=([^;]+)", conn_str, re.IGNORECASE)
    if not m:
        return
    dbname = m.group(1).strip()
    if dbname.lower() == "master":
        return
    master_conn = re.sub(r"Database=[^;]+", "Database=master", conn_str, flags=re.IGNORECASE)
    try:
        with pyodbc.connect(master_conn, autocommit=True, timeout=30) as c:
            cur = c.cursor()
            cur.execute(f"IF DB_ID(N'{dbname}') IS NULL CREATE DATABASE [{dbname}]")
    except Exception as e:
        print(f"[migration] aviso: nao foi possivel garantir o database '{dbname}': {e}")


def aplicar_migrations() -> int:
    cfg = get_config()
    _garantir_database(cfg.historico_conn)

    aplicadas = 0
    with pyodbc.connect(cfg.historico_conn, autocommit=True, timeout=30) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            IF OBJECT_ID(N'tb_schema_version', N'U') IS NULL
            CREATE TABLE tb_schema_version (
                arquivo NVARCHAR(200) PRIMARY KEY,
                aplicado_em DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            )
            """
        )
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            cur.execute("SELECT 1 FROM tb_schema_version WHERE arquivo = ?", sql_file.name)
            if cur.fetchone():
                continue
            print(f"[migration] aplicando {sql_file.name}")
            for batch in _batches(sql_file.read_text(encoding="utf-8")):
                cur.execute(batch)
            cur.execute("INSERT INTO tb_schema_version (arquivo) VALUES (?)", sql_file.name)
            aplicadas += 1
    print(f"[migration] {aplicadas} aplicadas")
    return aplicadas
