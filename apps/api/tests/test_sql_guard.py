import pytest
from app.core.sql_guard import validar_sql_readonly, SqlNaoPermitidoError


def test_select_simples_passa():
    validar_sql_readonly("SELECT * FROM PreLeads WHERE Id = 1")


def test_select_com_join_passa():
    validar_sql_readonly("SELECT c.Nome FROM Clients c JOIN AspNetUsers u ON u.Id = c.UsuarioId")


def test_cte_passa():
    validar_sql_readonly("WITH x AS (SELECT 1 AS a) SELECT * FROM x")


@pytest.mark.parametrize("sql_proibido", [
    "DELETE FROM Clients WHERE Id = 1",
    "UPDATE PreLeads SET Nome = 'x'",
    "INSERT INTO Tarefas (Id) VALUES (1)",
    "DROP TABLE Clients",
    "ALTER TABLE Clients ADD COLUMN x INT",
    "TRUNCATE TABLE PreLeads",
    "EXEC sp_help",
    "MERGE INTO Clients USING t ON 1=1 WHEN MATCHED THEN DELETE",
    "SELECT * FROM Clients; DELETE FROM Clients",
])
def test_dml_ddl_bloqueado(sql_proibido):
    with pytest.raises(SqlNaoPermitidoError):
        validar_sql_readonly(sql_proibido)


def test_sql_invalido_bloqueado():
    with pytest.raises(SqlNaoPermitidoError):
        validar_sql_readonly("SLECT * FROM x")
