"""CR_FLUXO_CAIXA — fluxo de caixa unificado (ContasAPagar + ContasAReceber).

Abordagem híbrida (C): CTE fixa com JOINs canônicos; LLM compõe SELECT/WHERE/GROUP BY/ORDER BY
escolhendo colunas declaradas na ontologia.

Referência: Docs/APOLO_DISCOVERY/02-CR-discovery.md
"""
from app.domains import registrar
from app.domains._base import Dominio, Ramo, Coluna, FewShot


# ============================================================
# Colunas do resultado (saída do CTE) — LLM escolhe daqui no SELECT
# ============================================================

COL_TIPO = Coluna(
    alias="tipo", expr="tipo", tipo="enum",
    descricao="Origem do registro: 'pagar' (ContasAPagar) ou 'receber' (ContasAReceber).",
    nullable=False, dimensao=True, enum_valores=("pagar", "receber"),
)
COL_ID = Coluna(
    alias="id", expr="id", tipo="str",
    descricao="Id da conta (ContasAPagar.Id ou ContasAReceber.Id, uniqueidentifier serializado).",
    nullable=False,
)
COL_VALOR = Coluna(
    alias="valor", expr="valor", tipo="decimal",
    descricao=(
        "Valor monetário da conta. Pagar = ContasAPagar.Pagamento; "
        "receber = COALESCE(ValorBoleto, ValorNota). Agregável com SUM/AVG."
    ),
    agregavel=True,
)
COL_DATA_VENCIMENTO = Coluna(
    alias="data_vencimento", expr="data_vencimento", tipo="datetime",
    descricao=(
        "COMPETÊNCIA (Periodo da folha mensal — mês/ano de referência), NÃO uma data "
        "de vencimento contratual do boleto/pagamento. 'atrasada' significa competência "
        "vencida sem quitação (inadimplência por competência), não vencimento de contrato. "
        "Use comparadores >=, <=, BETWEEN e YEAR/MONTH pra agrupar por mês."
    ),
    dimensao=True,
)
COL_DATA_PAGAMENTO = Coluna(
    alias="data_pagamento", expr="data_pagamento", tipo="datetime",
    descricao=(
        "Data efetiva de quitação (DataProcesso pra pagar, DataPgBoleto pra receber). "
        "NULL quando ainda não foi paga/recebida. Esta é a definição de 'pago/recebido' "
        "do domínio (data NOT NULL = quitada) e PODE divergir do campo Status textual."
    ),
    dimensao=True,
)
COL_ATRASADA = Coluna(
    alias="atrasada", expr="atrasada", tipo="bool",
    descricao=(
        "Flag derivada: 1 quando data_vencimento < GETDATE() AND data_pagamento IS NULL. "
        "0 = em dia ou já quitada."
    ),
    nullable=False, dimensao=True,
)
COL_STATUS = Coluna(
    alias="status", expr="status", tipo="enum",
    descricao=(
        "Status textual original da tabela (campo Status de ContasAPagar/AReceber). "
        "Valores reais por ramo — pagar: 'Pago', 'Pendente', 'Faturado'. "
        "receber: 'Pago', 'Faturado', 'Aguardando', 'Não Aprovado', 'Negociação', "
        "'Pendente', 'Full' (e NULL). NÃO filtre por valores fora desta lista. "
        "Atenção: Status pode divergir das datas de quitação (ex.: há contas com "
        "Status='Pendente' já processadas e 'Pago' sem data de recebimento)."
    ),
    dimensao=True,
    enum_valores=(
        "Pago", "Pendente", "Faturado", "Aguardando",
        "Não Aprovado", "Negociação", "Full",
    ),
)
COL_CATEGORIA = Coluna(
    alias="categoria", expr="categoria", tipo="str",
    descricao=(
        "Categoria financeira. NULL nas folhas mensais — categorização só existe em "
        "LancamentoPagamentos (fora deste domínio). Coluna mantida pra simetria."
    ),
    dimensao=True,
)
COL_FAVORECIDO = Coluna(
    alias="favorecido", expr="favorecido", tipo="str",
    descricao=(
        "Nome do favorecido. Pagar = NomeCompleto do colaborador; "
        "receber = Nome da empresa cliente."
    ),
    dimensao=True,
)
COL_COLABORADOR = Coluna(
    alias="colaborador", expr="colaborador", tipo="str",
    descricao="Nome do colaborador beneficiário (só pra tipo='pagar'; NULL no ramo receber).",
    dimensao=True,
)
COL_EMPRESA_CLIENTE = Coluna(
    alias="empresa_cliente", expr="empresa_cliente", tipo="str",
    descricao="Nome da empresa cliente pagadora (só pra tipo='receber'; NULL no ramo pagar).",
    dimensao=True,
)
COL_EMPRESA_ORIGEM = Coluna(
    alias="empresa_origem", expr="empresa_origem", tipo="str",
    descricao=(
        "Empresa de origem/faturamento. Pagar = cp.EmpresaOrigem (texto livre); "
        "receber = EmpresaOrigens.Nome (via EmpresaOrigemId). Use LIKE '%texto%' "
        "ou GROUP BY pra agrupar recebíveis/pagamentos por empresa de origem."
    ),
    dimensao=True,
)


# ============================================================
# Colunas filtráveis dos ramos — LLM usa aqui pra montar WHERE
# ============================================================

FILTROS_PAGAR = (
    Coluna(alias="data_vencimento", expr="cp.Periodo", tipo="datetime",
           descricao="Período/vencimento da conta a pagar. Use >=, <=, BETWEEN, YEAR(...), MONTH(...)."),
    Coluna(alias="data_pagamento", expr="cp.DataProcesso", tipo="datetime",
           descricao="Data de processamento/pagamento. IS NULL = ainda não paga."),
    Coluna(alias="valor", expr="cp.Pagamento", tipo="decimal",
           descricao="Valor a pagar (money)."),
    Coluna(alias="status", expr="cp.Status", tipo="str",
           descricao="Status textual da ContaAPagar."),
    Coluna(alias="colaborador", expr="col.NomeCompleto", tipo="str",
           descricao="Nome do colaborador beneficiário. Use LIKE '%texto%'."),
    Coluna(alias="favorecido", expr="col.NomeCompleto", tipo="str",
           descricao="Para pagar, favorecido = colaborador."),
    Coluna(alias="ano", expr="cp.NrAno", tipo="int",
           descricao="Ano da folha (NrAno)."),
    Coluna(alias="mes", expr="cp.NrMes", tipo="int",
           descricao="Mês da folha (NrMes 1..12)."),
    Coluna(alias="empresa_origem", expr="cp.EmpresaOrigem", tipo="str",
           descricao="Empresa origem do pagamento (string livre)."),
)

FILTROS_RECEBER = (
    Coluna(alias="data_vencimento", expr="cr.Periodo", tipo="datetime",
           descricao="Período/vencimento da conta a receber."),
    Coluna(alias="data_pagamento", expr="cr.DataPgBoleto", tipo="datetime",
           descricao="Data de recebimento do boleto. IS NULL = ainda não recebida."),
    Coluna(alias="valor", expr="COALESCE(cr.ValorBoleto, cr.ValorNota)", tipo="decimal",
           descricao="Valor a receber (boleto, fallback nota)."),
    Coluna(alias="status", expr="cr.Status", tipo="str",
           descricao="Status textual da ContaAReceber."),
    Coluna(alias="empresa_cliente", expr="emp.Nome", tipo="str",
           descricao="Nome da empresa cliente pagadora. Use LIKE '%texto%'."),
    Coluna(alias="favorecido", expr="emp.Nome", tipo="str",
           descricao="Para receber, favorecido = empresa cliente."),
    Coluna(alias="ano", expr="cr.NrAno", tipo="int",
           descricao="Ano da folha (NrAno)."),
    Coluna(alias="mes", expr="cr.NrMes", tipo="int",
           descricao="Mês da folha (NrMes 1..12)."),
    Coluna(alias="empresa_origem", expr="eo.Nome", tipo="str",
           descricao="Empresa de origem/faturamento do recebível (EmpresaOrigens.Nome). Use LIKE '%texto%'."),
)


# ============================================================
# CTE template — JOINs canônicos, LLM nunca altera
# ============================================================

CTE = """
SELECT 'pagar' AS tipo,
       CAST(cp.Id AS NVARCHAR(36)) AS id,
       cp.Pagamento AS valor,
       cp.Periodo AS data_vencimento,
       cp.DataProcesso AS data_pagamento,
       CAST(CASE WHEN cp.Periodo < GETDATE() AND cp.DataProcesso IS NULL THEN 1 ELSE 0 END AS BIT) AS atrasada,
       cp.Status AS status,
       CAST(NULL AS NVARCHAR(255)) AS categoria,
       col.NomeCompleto AS favorecido,
       col.NomeCompleto AS colaborador,
       CAST(NULL AS NVARCHAR(255)) AS empresa_cliente,
       cp.EmpresaOrigem AS empresa_origem
FROM ContasAPagar cp
LEFT JOIN Colaboradores col ON col.Id = cp.ColaboradorId
WHERE ({FILTROS_PAGAR})

UNION ALL

SELECT 'receber' AS tipo,
       CAST(cr.Id AS NVARCHAR(36)) AS id,
       COALESCE(cr.ValorBoleto, cr.ValorNota) AS valor,
       cr.Periodo AS data_vencimento,
       cr.DataPgBoleto AS data_pagamento,
       CAST(CASE WHEN cr.Periodo < GETDATE() AND cr.DataPgBoleto IS NULL THEN 1 ELSE 0 END AS BIT) AS atrasada,
       cr.Status AS status,
       CAST(NULL AS NVARCHAR(255)) AS categoria,
       emp.Nome AS favorecido,
       CAST(NULL AS NVARCHAR(255)) AS colaborador,
       emp.Nome AS empresa_cliente,
       eo.Nome AS empresa_origem
FROM ContasAReceber cr
LEFT JOIN Empresas emp ON emp.Id = cr.EmpresaId
LEFT JOIN EmpresaOrigens eo ON eo.Id = cr.EmpresaOrigemId
WHERE ({FILTROS_RECEBER})
""".strip()


# ============================================================
# Few-shot examples — calibram o LLM no estilo de resposta
# ============================================================

FEW_SHOTS = (
    FewShot(
        pergunta="Total a pagar este mes",
        sql='{"wheres":{"pagar":"cp.NrAno = YEAR(GETDATE()) AND cp.NrMes = MONTH(GETDATE()) AND cp.Pagamento > 0","receber":"1=0"},'
            '"select_list":"ROUND(SUM(valor), 2) AS total_pagar","group_by":"","order_by":"","top":1,'
            '"explicacao_curta":"Soma o Pagamento (>0) das contas a pagar do mês corrente"}',
        explicacao="Filtra só ramo pagar (receber=1=0). Agrega SUM com higiene Pagamento > 0 (exclui lixo R$0). NrAno/NrMes batem com a folha mensal.",
    ),
    FewShot(
        pergunta="Contas vencidas ha mais de 30 dias por favorecido",
        sql='{"wheres":{"pagar":"cp.Periodo <= DATEADD(day,-30,GETDATE()) AND cp.DataProcesso IS NULL AND cp.NrAno >= 2020 AND cp.Pagamento > 0",'
            '"receber":"cr.Periodo <= DATEADD(day,-30,GETDATE()) AND cr.DataPgBoleto IS NULL AND cr.NrAno >= 2020 AND COALESCE(cr.ValorBoleto, cr.ValorNota) > 0"},'
            '"select_list":"favorecido, tipo, ROUND(SUM(valor), 2) AS total_atrasado, COUNT(*) AS qtd",'
            '"group_by":"favorecido, tipo","order_by":"total_atrasado DESC","top":50,'
            '"explicacao_curta":"Ranking de inadimplência por competência por favorecido nos dois ramos"}',
        explicacao="Atrasada = competência <= -30d AND pagamento IS NULL. Higiene NrAno>=2020 e valor>0 exclui lixo de conversão. UNION mostra os dois ramos. GROUP BY favorecido+tipo.",
    ),
    FewShot(
        pergunta="Faturamento total recebido em 2026 por empresa cliente",
        sql='{"wheres":{"pagar":"1=0","receber":"cr.DataPgBoleto IS NOT NULL AND YEAR(cr.DataPgBoleto) = 2026 AND COALESCE(cr.ValorBoleto, cr.ValorNota) > 0"},'
            '"select_list":"empresa_cliente, ROUND(SUM(valor), 2) AS faturamento","group_by":"empresa_cliente","order_by":"faturamento DESC","top":100,'
            '"explicacao_curta":"Recebimentos confirmados (DataPgBoleto preenchida) em 2026 agrupados por empresa cliente"}',
        explicacao="Só ramo receber. 'Recebido' = DataPgBoleto NOT NULL (definição por data, pode divergir de Status). YEAR=2026 e valor>0 (higiene). GROUP BY empresa_cliente.",
    ),
    FewShot(
        pergunta="Fluxo de caixa do mes entradas vs saidas",
        sql='{"wheres":{"pagar":"cp.NrAno = YEAR(GETDATE()) AND cp.NrMes = MONTH(GETDATE()) AND cp.Pagamento > 0",'
            '"receber":"cr.NrAno = YEAR(GETDATE()) AND cr.NrMes = MONTH(GETDATE()) AND COALESCE(cr.ValorBoleto, cr.ValorNota) > 0"},'
            '"select_list":"tipo, ROUND(SUM(valor), 2) AS total, ROUND(SUM(CASE WHEN atrasada = 1 THEN valor ELSE 0 END), 2) AS total_atrasado",'
            '"group_by":"tipo","order_by":"tipo","top":2,'
            '"explicacao_curta":"Comparativo entradas (receber) vs saídas (pagar) do mês corrente"}',
        explicacao="Ambos os ramos no mês corrente, com higiene valor>0. GROUP BY tipo dá 2 linhas: pagar / receber.",
    ),
    FewShot(
        pergunta="Recebiveis por empresa de origem em 2026",
        sql='{"wheres":{"pagar":"1=0","receber":"cr.NrAno = 2026 AND COALESCE(cr.ValorBoleto, cr.ValorNota) > 0"},'
            '"select_list":"empresa_origem, ROUND(SUM(valor), 2) AS total_receber, COUNT(*) AS qtd","group_by":"empresa_origem","order_by":"total_receber DESC","top":50,'
            '"explicacao_curta":"Total a receber em 2026 agrupado por empresa de origem/faturamento"}',
        explicacao="Só ramo receber. empresa_origem = EmpresaOrigens.Nome (via EmpresaOrigemId). Higiene valor>0. GROUP BY empresa_origem.",
    ),
)


# ============================================================
# Dominio cravado
# ============================================================

CR_FLUXO_CAIXA = registrar(Dominio(
    nome="CR_FLUXO_CAIXA",
    descricao=(
        "Fluxo de caixa unificado da Prover: contas a pagar (folha de colaboradores) "
        "e contas a receber (boletos/notas de empresas clientes). "
        "Use quando a pergunta envolver pagar, receber, despesa, receita, fatura, "
        "vencimento, atraso, inadimplência, fluxo, caixa, favorecido, valor financeiro, "
        "folha financeira."
    ),
    palavras_chave=(
        "pagar, receber, despesa, receita, fatura, vencimento, atraso, fluxo, caixa, "
        "conta, favorecido, financeiro, inadimplencia, boleto, "
        "pagamento, recebimento, faturamento, empresa de origem"
    ),
    base_conexao="cr",
    permissoes_necessarias=("financeiro",),
    cte_template=CTE,
    cte_alias="fluxo",
    tabelas_whitelist=(
        "ContasAPagar", "ContasAReceber",
        "Colaboradores", "Empresas", "EmpresaOrigens",
    ),
    ramos=(
        Ramo(
            nome="pagar", placeholder="FILTROS_PAGAR",
            descricao="Saídas — contas a pagar (folha mensal de colaboradores).",
            colunas_filtraveis=FILTROS_PAGAR,
        ),
        Ramo(
            nome="receber", placeholder="FILTROS_RECEBER",
            descricao="Entradas — contas a receber (boletos/notas de empresas clientes).",
            colunas_filtraveis=FILTROS_RECEBER,
        ),
    ),
    colunas_resultado=(
        COL_TIPO, COL_ID, COL_VALOR, COL_DATA_VENCIMENTO, COL_DATA_PAGAMENTO,
        COL_ATRASADA, COL_STATUS, COL_CATEGORIA, COL_FAVORECIDO,
        COL_COLABORADOR, COL_EMPRESA_CLIENTE, COL_EMPRESA_ORIGEM,
    ),
    few_shots=FEW_SHOTS,
    rules="""
- "Pagar" = ContasAPagar (saída, folha mensal de colaborador). "Receber" = ContasAReceber (entrada, boleto/nota de empresa cliente).
- Para incluir só pagar: wheres.pagar = filtros; wheres.receber = "1=0".
- Para incluir só receber: wheres.pagar = "1=0"; wheres.receber = filtros.
- Para fluxo de caixa completo: filtros equivalentes nos dois ramos (mesmo período em ambos).
- data_vencimento = Periodo, que é a COMPETÊNCIA (mês/ano de referência da folha), NÃO um vencimento contratual. NrAno + NrMes são duplicados úteis pra filtros rápidos.
- data_pagamento = DataProcesso (pagar) / DataPgBoleto (receber). NULL = ainda em aberto.
- "Pago/recebido/quitado" no domínio = data de quitação preenchida (DataProcesso/DataPgBoleto IS NOT NULL); "em aberto" = data IS NULL. Esta definição por DATA pode DIVERGIR do campo Status textual (há contas com Status='Pendente' já processadas e Status='Pago' sem data de recebimento). Se o usuário falar em pago/recebido, use a data; se citar explicitamente Status, use o campo Status e avise da possível divergência.
- Status reais por ramo (filtre só por estes; não invente valores): pagar = 'Pago', 'Pendente', 'Faturado'. receber = 'Pago', 'Faturado', 'Aguardando', 'Não Aprovado', 'Negociação', 'Pendente', 'Full' (e NULL).
- atrasada = 1 quando data_vencimento (competência) < GETDATE() AND data_pagamento IS NULL. Já vem pronta no CTE. Semanticamente é INADIMPLÊNCIA POR COMPETÊNCIA (competência vencida sem quitação), não vencimento de contrato.
- valor: pagar usa cp.Pagamento; receber usa COALESCE(cr.ValorBoleto, cr.ValorNota).
- HIGIENE DE DADOS: há registros-lixo de conversão — contas a pagar com valor <= 0 (~49, somam R$0) e linhas com NrAno=1 (datas-lixo) e algumas com Periodo no futuro. Em SOMAS/MÉDIAS/RANKINGS de fluxo, aplique WHERE valor > 0 AND NrAno >= 2020 (ou Periodo válido) para não distorcer totais e buckets de ano '1' espúrios.
- favorecido: pagar = NomeCompleto do colaborador; receber = Nome da empresa cliente.
- empresa_origem: pagar = cp.EmpresaOrigem (texto livre); receber = EmpresaOrigens.Nome (via EmpresaOrigemId). Disponível para SELECT/GROUP BY/WHERE nos dois ramos.
- categoria/imposto NÃO são suportados neste domínio: categoria fica sempre NULL (ContasAPagar/AReceber não têm FK pra Categorias — essa relação vive em LancamentoPagamentos, fora de escopo) e não existe coluna de imposto. Se a pergunta for sobre categoria financeira ou imposto, avise o usuário que não há cobertura em vez de devolver NULL silencioso.
- Para agrupar por mês: GROUP BY YEAR(data_vencimento), MONTH(data_vencimento) — ou usar ano/mes filtráveis nos ramos.
- Money/decimal: arredondar com ROUND(SUM(valor), 2) ao exibir totais.
""".strip(),
))
