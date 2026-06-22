from app.domains._base import Dominio, Ramo, Coluna


def test_dominio_simples_um_ramo():
    d = Dominio(
        nome="TESTE",
        descricao="dominio de teste",
        palavras_chave="teste,exemplo",
        base_conexao="crm",
        cte_template="SELECT * FROM x WHERE ({FILTROS})",
        ramos=(
            Ramo(
                nome="principal",
                placeholder="FILTROS",
                descricao="ramo principal",
                colunas_filtraveis=(
                    Coluna(alias="vendedor", expr="u.Email", tipo="str", descricao="email do vendedor"),
                ),
            ),
        ),
    )
    assert d.nome == "TESTE"
    assert len(d.ramos) == 1
    assert d.ramos[0].placeholder == "FILTROS"
    assert d.ramos[0].colunas_filtraveis[0].expr == "u.Email"


def test_dominio_multi_ramo():
    d = Dominio(
        nome="MULTI",
        descricao="x",
        palavras_chave="y",
        base_conexao="cr",
        cte_template="WITH pagar AS ({FILTROS_PAGAR}) UNION ALL SELECT * FROM ({FILTROS_RECEBER})",
        ramos=(
            Ramo(
                nome="pagar",
                placeholder="FILTROS_PAGAR",
                colunas_filtraveis=(
                    Coluna(alias="data_vencimento", expr="DataVencimento", tipo="date", descricao="vencimento"),
                ),
            ),
            Ramo(
                nome="receber",
                placeholder="FILTROS_RECEBER",
                colunas_filtraveis=(
                    Coluna(alias="empresa", expr="e.NomeFantasia", tipo="str", descricao="empresa"),
                ),
            ),
        ),
    )
    assert len(d.ramos) == 2
    assert d.ramos[1].nome == "receber"
    assert d.ramos[1].colunas_filtraveis[0].alias == "empresa"
