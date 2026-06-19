from app.domains._base import Dominio, Ramo


def test_dominio_simples_um_ramo():
    d = Dominio(
        nome="TESTE",
        descricao="dominio de teste",
        palavras_chave="teste,exemplo",
        base_conexao="crm",
        query_base="SELECT * FROM x WHERE {FILTROS}",
        ramos=(Ramo("principal", "FILTROS", {"vendedor": "u.Email"}),),
    )
    assert d.nome == "TESTE"
    assert len(d.ramos) == 1
    assert d.ramos[0].map_filtros["vendedor"] == "u.Email"


def test_dominio_multi_ramo():
    d = Dominio(
        nome="MULTI",
        descricao="x",
        palavras_chave="y",
        base_conexao="cr",
        query_base="WITH a AS (...), b AS (...) SELECT * FROM a UNION ALL SELECT * FROM b",
        cte_template="WITH pagar AS ({FILTROS_PAGAR}) UNION receber AS ({FILTROS_RECEBER})",
        ramos=(
            Ramo("pagar", "FILTROS_PAGAR", {"data_vencimento": "DataVencimento"}),
            Ramo("receber", "FILTROS_RECEBER", {"empresa": "e.NomeFantasia"}),
        ),
    )
    assert len(d.ramos) == 2
