import argparse
import psycopg
from datetime import datetime, timedelta
from app.core.config import get_config

def run(periodo_dias: int):
    cfg = get_config()
    desde = datetime.utcnow() - timedelta(days=periodo_dias)
    with psycopg.connect(cfg.postgres_conn) as conn:
        with conn.cursor() as cur:
            print(f"=== APOLO_PROVER · stats últimos {periodo_dias} dias ===\n")

            cur.execute("SELECT COUNT(*) FROM tb_pergunta WHERE created_at >= %s", (desde,))
            print(f"Perguntas: {cur.fetchone()[0]}")

            cur.execute("SELECT dominio, COUNT(*) FROM tb_pergunta WHERE created_at >= %s AND dominio IS NOT NULL GROUP BY dominio ORDER BY 2 DESC", (desde,))
            print("\nPor domínio:")
            for d, c in cur.fetchall():
                print(f"  {d}: {c}")

            cur.execute("""
                SELECT COUNT(*) FILTER (WHERE r.erro IS NOT NULL),
                       AVG(r.latencia_ms),
                       SUM(r.custo_estimado),
                       SUM(r.tokens_input), SUM(r.tokens_output)
                FROM tb_pergunta p JOIN tb_resposta r ON r.pergunta_id = p.id
                WHERE p.created_at >= %s
            """, (desde,))
            erros, lat, custo, tin, tout = cur.fetchone()
            print(f"\nErros: {erros or 0}")
            print(f"Latência média: {lat or 0:.0f} ms")
            print(f"Custo total: US$ {custo or 0:.2f}")
            print(f"Tokens: in={tin or 0:,} out={tout or 0:,}")

            cur.execute("SELECT canal, COUNT(*) FROM tb_pergunta WHERE created_at >= %s GROUP BY canal", (desde,))
            print("\nPor canal:")
            for c, n in cur.fetchall():
                print(f"  {c}: {n}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--periodo", type=int, default=7)
    args = parser.parse_args()
    run(args.periodo)
