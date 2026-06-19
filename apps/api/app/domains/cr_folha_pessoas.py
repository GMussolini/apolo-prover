"""CR_FOLHA_PESSOAS - folha de pagamento + custo de pessoas.

Abordagem hibrida (C): CTE fixa com JOINs canonicos; LLM compoe SELECT/WHERE/GROUP BY/ORDER BY
escolhendo colunas declaradas na ontologia.

Referencia: Docs/APOLO_DISCOVERY/02-CR-discovery.md
"""
from app.domains import registrar
from app.domains._base import Dominio, Ramo, Coluna, FewShot


# ============================================================
# Colunas do resultado (saida do CTE) - LLM escolhe daqui no SELECT
# ============================================================

COL_FOLHA_ID = Coluna(
    alias="FolhaId", expr="FolhaId", tipo="str",
    descricao="Id (uniqueidentifier) da linha em Folhas.",
    nullable=False,
)
COL_MES_REFERENCIA = Coluna(
    alias="MesReferencia", expr="MesReferencia", tipo="int",
    descricao="Mes de referencia da folha (1..12). Folhas.NrMes.",
    nullable=False, dimensao=True,
)
COL_ANO_REFERENCIA = Coluna(
    alias="AnoReferencia", expr="AnoReferencia", tipo="int",
    descricao="Ano de referencia da folha (ex: 2026). Folhas.NrAno.",
    nullable=False, dimensao=True,
)
COL_FATURAMENTO = Coluna(
    alias="faturamento", expr="faturamento", tipo="decimal",
    descricao="FATURAMENTO de UMA linha de folha (colaborador x competencia x projeto/alocacao), Folhas.VlTotalProj = RECEITA que a pessoa gera, NAO o salario dela. ATENCAO: ha VARIAS linhas por colaborador na mesma competencia (uma por projeto) - SOME por colaborador para obter o total da pessoa. 'Dev que mais fatura' = SUM(faturamento) por colaborador. Agregavel.",
    agregavel=True,
)
COL_MARGEM = Coluna(
    alias="margem", expr="margem", tipo="decimal",
    descricao="Margem de UMA linha de folha = faturamento - custo (Folhas.VlTotalProj - Folhas.VlTotalCusto). Ha varias linhas por colaborador na competencia (uma por projeto); SOME por colaborador. Agregavel.",
    agregavel=True,
)
COL_CUSTO = Coluna(
    alias="custo", expr="custo", tipo="decimal",
    descricao="CUSTO efetivo de UMA linha de folha (colaborador x competencia x projeto/alocacao), Folhas.VlTotalCusto = quanto a pessoa custa. ATENCAO: ha VARIAS linhas por colaborador na mesma competencia (uma por projeto) - SOME por colaborador para obter o total da pessoa. 'Folha/custo total' = SUM(custo). Agregavel.",
    agregavel=True,
)
COL_COLABORADOR_NOME = Coluna(
    alias="colaborador_nome", expr="colaborador_nome", tipo="str",
    descricao="Nome completo do colaborador dono do holerite (Colaboradores.NomeCompleto).",
    dimensao=True,
)
COL_COLABORADOR_EMAIL = Coluna(
    alias="colaborador_email", expr="colaborador_email", tipo="str",
    descricao="E-mail do colaborador dono do holerite.",
    dimensao=True,
)
COL_CARGO = Coluna(
    alias="cargo", expr="cargo", tipo="str",
    descricao="Cargo do colaborador (Cargos.Nome).",
    dimensao=True,
)
COL_DEPARTAMENTO = Coluna(
    alias="departamento", expr="departamento", tipo="str",
    descricao="Departamento do colaborador, obtido via Cargo (Departamentos.Nome).",
    dimensao=True,
)
COL_DELIVERY_MANAGER = Coluna(
    alias="delivery_manager", expr="delivery_manager", tipo="str",
    descricao="Nome do Delivery Manager associado a folha (contexto, NAO recebe holerite).",
    dimensao=True,
)
COL_TECH_LEAD = Coluna(
    alias="tech_lead", expr="tech_lead", tipo="str",
    descricao="Nome do Tech Lead associado a folha (contexto, NAO recebe holerite).",
    dimensao=True,
)
COL_MOTIVO_DESLIGAMENTO = Coluna(
    alias="motivo_desligamento", expr="motivo_desligamento", tipo="str",
    descricao="Motivo de desligamento do colaborador (MotivoDesligamento.Descricao). NULL = ainda ativo.",
    dimensao=True,
)
COL_TIPO_FOLHA = Coluna(
    alias="tipo_folha", expr="tipo_folha", tipo="int",
    descricao="Tipo/categoria da linha de folha (codigo inteiro - Folhas.TipoFolha). Significado dos codigos NAO documentado; pode haver tipos que nao sao folha de pagamento padrao. Sem filtro fixo no CTE: todas as somas de faturamento/custo/margem incluem todos os tipos. Use SELECT DISTINCT tipo_folha para descobrir os valores.",
    dimensao=True,
)


# ============================================================
# Colunas filtraveis do ramo - LLM usa aqui pra montar WHERE
# ============================================================

FILTROS_PRINCIPAL = (
    Coluna(alias="colaborador_nome", expr="col.NomeCompleto", tipo="str",
           descricao="Nome do colaborador dono do holerite. Use LIKE '%texto%'."),
    Coluna(alias="colaborador_email", expr="col.Email", tipo="str",
           descricao="E-mail do colaborador dono do holerite."),
    Coluna(alias="cargo", expr="cargo.Nome", tipo="str",
           descricao="Nome do cargo."),
    Coluna(alias="departamento", expr="dep.Nome", tipo="str",
           descricao="Nome do departamento."),
    Coluna(alias="delivery_manager", expr="dm.NomeCompleto", tipo="str",
           descricao="Nome do Delivery Manager (Folhas.ColaboradorDeliveryManagerId)."),
    Coluna(alias="tech_lead", expr="tl.NomeCompleto", tipo="str",
           descricao="Nome do Tech Lead (Folhas.ColaboradorTechLeadId)."),
    Coluna(alias="motivo_desligamento", expr="md.Descricao", tipo="str",
           descricao="Descricao do motivo de desligamento."),
    Coluna(alias="mes_referencia", expr="f.NrMes", tipo="int",
           descricao="Mes de referencia da folha (1..12)."),
    Coluna(alias="ano_referencia", expr="f.NrAno", tipo="int",
           descricao="Ano de referencia da folha (ex: 2026)."),
    Coluna(alias="referencia", expr="f.Referencia", tipo="datetime",
           descricao="Data de referencia completa da folha. Use comparadores >=, <=, BETWEEN."),
    Coluna(alias="faturamento", expr="f.VlTotalProj", tipo="decimal",
           descricao="Faturamento do colaborador no projeto (VlTotalProj) = receita gerada. Use comparadores >=, <=."),
    Coluna(alias="custo", expr="f.VlTotalCusto", tipo="decimal",
           descricao="Custo efetivo do colaborador (VlTotalCusto) = quanto a pessoa custa."),
    Coluna(alias="desligado", expr="(CASE WHEN col.MotivoDesligamentoId IS NOT NULL THEN 1 ELSE 0 END)",
           tipo="int", descricao="1 = colaborador desligado, 0 = ativo."),
    Coluna(alias="colaborador_ativo", expr="col.Ativo", tipo="bool",
           descricao="Flag de colaborador ativo (1 = ativo)."),
    Coluna(alias="tipo_folha", expr="f.TipoFolha", tipo="int",
           descricao="Tipo/categoria da linha de folha (codigo inteiro - Folhas.TipoFolha). Significado dos codigos NAO documentado; pode incluir tipos que nao sao folha de pagamento padrao (ex.: provisao, ajuste, estorno). Use SELECT DISTINCT TipoFolha para descobrir os valores antes de filtrar."),
)


# ============================================================
# CTE template - JOINs canonicos, LLM nunca altera
# ============================================================

CTE = """
SELECT f.Id AS FolhaId,
       f.NrMes AS MesReferencia,
       f.NrAno AS AnoReferencia,
       CAST(f.VlTotalProj AS decimal(18,2)) AS faturamento,
       CAST((ISNULL(f.VlTotalProj,0) - ISNULL(f.VlTotalCusto,0)) AS decimal(18,2)) AS margem,
       CAST(f.VlTotalCusto AS decimal(18,2)) AS custo,
       col.NomeCompleto AS colaborador_nome,
       col.Email        AS colaborador_email,
       cargo.Nome       AS cargo,
       dep.Nome         AS departamento,
       dm.NomeCompleto  AS delivery_manager,
       tl.NomeCompleto  AS tech_lead,
       md.Descricao     AS motivo_desligamento,
       f.TipoFolha      AS tipo_folha
FROM Folhas f
INNER JOIN Colaboradores col       ON col.Id = f.ColaboradorId
LEFT  JOIN Colaboradores dm        ON dm.Id  = f.ColaboradorDeliveryManagerId
LEFT  JOIN Colaboradores tl        ON tl.Id  = f.ColaboradorTechLeadId
LEFT  JOIN Cargos cargo            ON cargo.Id = col.CargoId
LEFT  JOIN Departamentos dep       ON dep.Id   = cargo.DepartamentoId
LEFT  JOIN MotivoDesligamento md   ON md.Id    = col.MotivoDesligamentoId
WHERE ({FILTROS_PRINCIPAL})
""".strip()


# ============================================================
# Few-shot examples - calibram o LLM no estilo de resposta
# ============================================================

FEW_SHOTS = (
    FewShot(
        pergunta="Custo total da folha do mes 5 de 2026",
        sql='{"wheres":{"principal":"f.NrMes = 5 AND f.NrAno = 2026"},'
            '"select_list":"SUM(custo) AS total_custo","group_by":"","order_by":"","top":1,'
            '"explicacao_curta":"Soma do custo para a competencia mai/2026"}',
        explicacao="Filtro por mes e ano. SUM(custo) agregado, top=1.",
    ),
    FewShot(
        pergunta="Qual desenvolvedor mais faturou nesse ano?",
        sql='{"wheres":{"principal":"f.NrAno = YEAR(GETDATE())"},'
            '"select_list":"colaborador_nome, SUM(faturamento) AS total_faturado","group_by":"colaborador_nome","order_by":"total_faturado DESC","top":10,'
            '"explicacao_curta":"Ranking de colaboradores por faturamento (VlTotalProj) no ano atual"}',
        explicacao="FATURAMENTO POR PESSOA = SUM(faturamento) por colaborador (faturamento=VlTotalProj). Soma a competencia inteira do ano, agrupa por colaborador. TOP 10 ranking.",
    ),
    FewShot(
        pergunta="Custo total da folha por departamento em 2026",
        sql='{"wheres":{"principal":"f.NrAno = 2026"},'
            '"select_list":"departamento, SUM(custo) AS custo_total",'
            '"group_by":"departamento","order_by":"custo_total DESC","top":50,'
            '"explicacao_curta":"Custo agregado da folha por departamento em 2026"}',
        explicacao="GROUP BY dimensao departamento + SUM(custo) + ORDER BY desc.",
    ),
    FewShot(
        pergunta="Faturamento por delivery manager nos ultimos 3 meses",
        sql='{"wheres":{"principal":"f.Referencia >= DATEADD(month,-3,GETDATE())"},'
            '"select_list":"delivery_manager, SUM(faturamento) AS total","group_by":"delivery_manager","order_by":"total DESC","top":100,'
            '"explicacao_curta":"Soma do faturamento por Delivery Manager nos ultimos 3 meses"}',
        explicacao="Filtro temporal por Referencia + GROUP BY delivery_manager + SUM(faturamento).",
    ),
    FewShot(
        pergunta="Qual o custo do colaborador Joao Silva no mes 5 de 2026?",
        sql='{"wheres":{"principal":"col.NomeCompleto LIKE \'%Joao Silva%\' AND f.NrMes = 5 AND f.NrAno = 2026"},'
            '"select_list":"colaborador_nome, SUM(custo) AS custo_total","group_by":"colaborador_nome","order_by":"custo_total DESC","top":10,'
            '"explicacao_curta":"Custo total do colaborador na competencia (soma das linhas de folha por projeto)"}',
        explicacao="Custo POR PESSOA: ha VARIAS linhas de folha por colaborador na mesma competencia (uma por projeto/alocacao). Use SEMPRE SUM(custo) GROUP BY colaborador_nome para obter o total da pessoa, NUNCA selecione custo sem SUM.",
    ),
)


# ============================================================
# Dominio cravado
# ============================================================

CR_FOLHA_PESSOAS = registrar(Dominio(
    nome="CR_FOLHA_PESSOAS",
    descricao=(
        "Folha de pagamento, FATURAMENTO e CUSTO por colaborador, por mes/ano. "
        "Cada colaborador (inclui desenvolvedores) tem por competencia: faturamento gerado no projeto "
        "(VlTotalProj), custo efetivo (VlTotalCusto) e margem. Cargo, departamento, delivery manager, "
        "tech lead, desligamento. Use quando a pergunta envolver: quanto um colaborador/desenvolvedor/dev "
        "FATURA ou CUSTA por mes/ano, faturamento/custo/margem POR PESSOA, ranking de quem mais fatura/custa, "
        "folha, salario, holerite, colaborador, funcionario, cargo, departamento, RH. "
        "IMPORTANTE: faturamento/custo POR COLABORADOR vem daqui (Folhas), NAO do valor de contrato do delivery. "
        "Aqui sao DESENVOLVEDORES/colaboradores da folha. Se a pergunta for sobre VENDEDOR (que faturou/vendeu/fechou), "
        "isso e CRM_PIPELINE (vendas), NAO esta folha."
    ),
    palavras_chave=(
        "faturamento, faturando, fatura, faturou, faturado, receita por pessoa, custo do colaborador, "
        "quanto fatura, quanto custa, desenvolvedor, dev, folha, salario, holerite, margem, colaborador, "
        "funcionario, custo, cargo, departamento, RH"
    ),
    base_conexao="cr",
    permissoes_necessarias=("rh",),
    cte_template=CTE,
    cte_alias="folha",
    tabelas_whitelist=(
        "Folhas", "Colaboradores", "Cargos", "Departamentos", "MotivoDesligamento",
    ),
    ramos=(
        Ramo(
            nome="principal", placeholder="FILTROS_PRINCIPAL",
            descricao="Linhas de Folhas (uma por colaborador x competencia).",
            colunas_filtraveis=FILTROS_PRINCIPAL,
        ),
    ),
    colunas_resultado=(
        COL_FOLHA_ID, COL_MES_REFERENCIA, COL_ANO_REFERENCIA,
        COL_FATURAMENTO, COL_MARGEM, COL_CUSTO,
        COL_COLABORADOR_NOME, COL_COLABORADOR_EMAIL,
        COL_CARGO, COL_DEPARTAMENTO,
        COL_DELIVERY_MANAGER, COL_TECH_LEAD,
        COL_MOTIVO_DESLIGAMENTO, COL_TIPO_FOLHA,
    ),
    few_shots=FEW_SHOTS,
    rules="""
- Folhas.ColaboradorId = DONO do holerite (a pessoa que recebe).
- ColaboradorDeliveryManagerId / ColaboradorTechLeadId / ColaboradorControladoId sao contexto de gestao, NAO recebem o holerite.
- FATURAMENTO de um colaborador/dev = SUM(faturamento) (faturamento=Folhas.VlTotalProj, a receita que a pessoa gera no projeto). "Dev que mais fatura no ano" = SUM(faturamento) por colaborador, f.NrAno=ano, ORDER BY desc.
- CUSTO de pessoal / "folha total do mes X" = SUM(custo) (custo=Folhas.VlTotalCusto) com f.NrMes=X e f.NrAno=ano.
- margem = faturamento - custo.
- NUNCA responda faturamento/custo por pessoa com valor de contrato (isso e CR_DELIVERY). Aqui e por colaborador x competencia.
- Mes/ano canonicos vem de Folhas.NrMes / Folhas.NrAno (inteiros); Folhas.Referencia eh a data completa equivalente.
- Departamento eh derivado via Cargo (Colaboradores -> Cargos -> Departamentos); Colaboradores nao tem DepartamentoId direto.
- Colaborador "desligado" = MotivoDesligamentoId IS NOT NULL OR Ativo = 0.
- ATENCAO GRANULARIDADE: Folhas tem MULTIPLAS linhas por colaborador na MESMA competencia (uma por projeto/alocacao, via Folhas.ProjetoId). Ex.: no mes 5/2026 ha 126 linhas para apenas 85 colaboradores distintos. Para custo/faturamento/margem POR PESSOA use SEMPRE SUM(...) agrupado por colaborador_nome (e mes/ano); NUNCA selecione custo/faturamento/margem sem SUM em consultas por pessoa, nem assuma que 1 linha = 1 pessoa/mes (uma linha e uma parcela por projeto, nao o total da pessoa).
- TipoFolha (Folhas.TipoFolha, int) classifica o tipo/categoria da linha de folha, mas o significado dos codigos NAO esta documentado. NAO ha filtro fixo no CTE, entao todas as somas incluem todos os tipos; se algum tipo nao for folha de pagamento padrao (provisao/ajuste/estorno) os totais podem incluir linhas indesejadas. Use SELECT DISTINCT tipo_folha para descobrir os valores antes de filtrar por tipo_folha.
- Emprestimos e cestas estao em tabelas separadas (EmprestimosColaboradores, CestasBasicas) - nao entram no CTE base.
- Acesso restrito a RH e admin (permissao 'rh').
""".strip(),
))
