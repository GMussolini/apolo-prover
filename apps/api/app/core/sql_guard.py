import sqlglot
from sqlglot import exp


class SqlNaoPermitidoError(Exception):
    pass


NODES_PROIBIDOS = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter,
    exp.TruncateTable, exp.Command, exp.Merge,
)


def validar_sql_readonly(sql: str) -> None:
    try:
        parsed = sqlglot.parse(sql, dialect="tsql")
    except Exception as e:
        raise SqlNaoPermitidoError(f"SQL invalido: {e}") from e

    if not parsed:
        raise SqlNaoPermitidoError("SQL vazio ou nao parseavel")

    if len(parsed) > 1:
        raise SqlNaoPermitidoError("Multiplos statements nao permitidos")

    for stmt in parsed:
        if stmt is None:
            raise SqlNaoPermitidoError("Statement nulo")
        if isinstance(stmt, NODES_PROIBIDOS):
            raise SqlNaoPermitidoError(f"Statement {type(stmt).__name__} nao permitido")
        for node in stmt.walk():
            if isinstance(node, NODES_PROIBIDOS):
                raise SqlNaoPermitidoError(f"Node {type(node).__name__} dentro do statement nao permitido")
