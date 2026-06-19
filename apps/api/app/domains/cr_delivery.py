"""CR_DELIVERY — alocacao de colaboradores em projetos/contratos do delivery.

Abordagem hibrida (C): CTE fixa com JOINs canonicos; LLM compoe SELECT/WHERE/GROUP BY/ORDER BY
escolhendo colunas declaradas na ontologia.

Referencia: Docs/APOLO_DISCOVERY/02-CR-discovery.md (secao ProjetoEmpresaColaboradores + Contratos).
"""
from app.domains import registrar
from app.domains._base import Dominio, Ramo, Coluna, FewShot


# ============================================================
# Colunas do resultado (saida do CTE) — LLM escolhe daqui no SELECT
# ============================================================

COL_ALOCACAO_ID = Coluna(
    alias="AlocacaoId", expr="AlocacaoId", tipo="str",
    descricao="Id da alocacao (ProjetoEmpresaColaboradores.Id, uniqueidentifier).",
    nullable=False,
)
COL_DATA_INICIO = Coluna(
    alias="DataInicio", expr="DataInicio", tipo="datetime",
    descricao="Data de inicio da alocacao do colaborador no projeto.",
    nullable=False, dimensao=True,
)
COL_DATA_FIM = Coluna(
    alias="DataFim", expr="DataFim", tipo="datetime",
    descricao="Data de fim da alocacao (NULL = alocacao ainda em vigor).",
    dimensao=True,
)
COL_HORAS_CONTRATADAS = Coluna(
    alias="HorasContratadas", expr="HorasContratadas", tipo="decimal",
    descricao=(
        "pec.Valor: representa HORAS mensais contratadas na MAIORIA das linhas (capacidade prevista, "
        "tipicamente 0-250), MAS a coluna e BIMODAL/mista: ~15 linhas guardam um VALOR FINANCEIRO (R$) "
        "que coincide com contrato_valor (ex.: valores acima de ~500 provavelmente sao financeiros). "
        "NAO somar cegamente (SUM mistura horas + R$ e gera total sem sentido) — filtre/avise antes de agregar."
    ),
    agregavel=True,
)
COL_COLABORADOR = Coluna(
    alias="colaborador", expr="colaborador", tipo="str",
    descricao="Nome completo do colaborador alocado.",
    dimensao=True,
)
COL_COLABORADOR_EMAIL = Coluna(
    alias="colaborador_email", expr="colaborador_email", tipo="str",
    descricao="E-mail do colaborador alocado.",
    dimensao=True,
)
COL_DELIVERY_MANAGER = Coluna(
    alias="delivery_manager", expr="delivery_manager", tipo="str",
    descricao="Nome do Delivery Manager responsavel pela alocacao.",
    dimensao=True,
)
COL_TECH_LEAD = Coluna(
    alias="tech_lead", expr="tech_lead", tipo="str",
    descricao="Nome do Tech Lead responsavel pela alocacao.",
    dimensao=True,
)
COL_CONTRATO_ID = Coluna(
    alias="ContratoId", expr="ContratoId", tipo="str",
    descricao="Id do contrato vinculado (Contratos.Id).",
)
COL_CONTRATO_INICIO = Coluna(
    alias="contrato_inicio", expr="contrato_inicio", tipo="datetime",
    descricao="Data de inicio do contrato.",
    dimensao=True,
)
COL_CONTRATO_FIM = Coluna(
    alias="contrato_fim", expr="contrato_fim", tipo="datetime",
    descricao="Data de encerramento do contrato (NULL = vigente).",
    dimensao=True,
)
COL_CONTRATO_VALOR = Coluna(
    alias="contrato_valor", expr="contrato_valor", tipo="decimal",
    descricao=(
        "Valor financeiro TOTAL do contrato (ct.Valor, money) — esta no GRAO DE CONTRATO, mas o CTE esta no "
        "grao de ALOCACAO (~4 alocacoes por contrato). NAO use SUM(contrato_valor) direto: multiplica o valor "
        "do contrato pelo numero de alocacoes (infla ~4x). Para total de contratos deduplique por ContratoId."
    ),
    agregavel=False,
)
COL_EMPRESA_CLIENTE = Coluna(
    alias="empresa_cliente", expr="empresa_cliente", tipo="str",
    descricao="Nome da empresa cliente onde o colaborador esta alocado.",
    dimensao=True,
)
COL_CENTRO_CUSTO = Coluna(
    alias="centro_custo", expr="centro_custo", tipo="str",
    descricao="Centro de custo vinculado ao contrato (CentroCustos.Nome).",
    dimensao=True,
)
COL_EMPRESA_ORIGEM = Coluna(
    alias="empresa_origem", expr="empresa_origem", tipo="str",
    descricao="Empresa origem (entidade de faturamento) do contrato (EmpresaOrigens.Nome via ct.EmpresaOrigemId).",
    dimensao=True,
)
COL_CUSTO_ALOCACAO = Coluna(
    alias="custo_alocacao", expr="custo_alocacao", tipo="decimal",
    descricao=(
        "Custo mensal do colaborador NESTA alocacao (pec.Custo, money). Use para perguntas de custo/margem "
        "do delivery (margem = contrato_valor - custo, atento ao grao de alocacao). NAO confundir com pec.Valor (horas)."
    ),
    agregavel=True,
)
COL_CUSTO_TECH_LEAD = Coluna(
    alias="custo_tech_lead", expr="custo_tech_lead", tipo="decimal",
    descricao="Custo financeiro do Tech Lead atribuido a esta alocacao (pec.CustoTechLead, money).",
    agregavel=True,
)
COL_CUSTO_DELIVERY_MANAGER = Coluna(
    alias="custo_delivery_manager", expr="custo_delivery_manager", tipo="decimal",
    descricao="Custo financeiro do Delivery Manager atribuido a esta alocacao (pec.CustoDeliveryManager, money).",
    agregavel=True,
)


# ============================================================
# Colunas filtraveis dos ramos — LLM usa aqui pra montar WHERE
# ============================================================

FILTROS_PRINCIPAL = (
    Coluna(alias="colaborador", expr="col.NomeCompleto", tipo="str",
           descricao="Nome do colaborador alocado. Use LIKE '%texto%'."),
    Coluna(alias="colaborador_email", expr="col.Email", tipo="str",
           descricao="E-mail do colaborador alocado."),
    Coluna(alias="delivery_manager", expr="dm.NomeCompleto", tipo="str",
           descricao="Nome do Delivery Manager."),
    Coluna(alias="tech_lead", expr="tl.NomeCompleto", tipo="str",
           descricao="Nome do Tech Lead."),
    Coluna(alias="empresa_cliente", expr="emp.Nome", tipo="str",
           descricao="Nome do cliente do delivery (Empresas.Nome)."),
    Coluna(alias="centro_custo", expr="cc.Nome", tipo="str",
           descricao="Centro de custo vinculado ao contrato."),
    Coluna(alias="empresa_origem", expr="eo.Nome", tipo="str",
           descricao="Empresa origem do contrato (faturamento)."),
    Coluna(alias="DataInicio", expr="pec.DataInicio", tipo="datetime",
           descricao="Inicio da alocacao. Use comparadores >=, <=, BETWEEN."),
    Coluna(alias="DataFim", expr="pec.DataFim", tipo="datetime",
           descricao="Fim da alocacao (NULL = vigente)."),
    Coluna(alias="contrato_inicio", expr="ct.DataInicio", tipo="datetime",
           descricao="Inicio do contrato."),
    Coluna(alias="contrato_fim", expr="ct.DataEncerramento", tipo="datetime",
           descricao="Encerramento do contrato (NULL = vigente)."),
    Coluna(alias="ativo", expr="pec.Ativo", tipo="bool",
           descricao="Flag de alocacao ativa (bit)."),
    Coluna(alias="contrato_ativo", expr="ct.IsAtivo", tipo="bool",
           descricao="Flag de contrato ativo (bit)."),
    Coluna(alias="HorasContratadas", expr="pec.Valor", tipo="decimal",
           descricao=(
               "pec.Valor: horas mensais na MAIORIA das linhas, MAS ~15 linhas guardam valor financeiro (R$) "
               "que coincide com contrato_valor (valores acima de ~500 provavelmente sao financeiros). "
               "NAO somar cegamente."
           )),
    Coluna(alias="custo_alocacao", expr="pec.Custo", tipo="decimal",
           descricao="Custo mensal do colaborador na alocacao (pec.Custo, money)."),
    Coluna(alias="custo_tech_lead", expr="pec.CustoTechLead", tipo="decimal",
           descricao="Custo do Tech Lead atribuido a esta alocacao (pec.CustoTechLead, money)."),
    Coluna(alias="custo_delivery_manager", expr="pec.CustoDeliveryManager", tipo="decimal",
           descricao="Custo do Delivery Manager atribuido a esta alocacao (pec.CustoDeliveryManager, money)."),
    Coluna(alias="contrato_valor", expr="ct.Valor", tipo="decimal",
           descricao=(
               "Valor financeiro TOTAL do contrato (money), no grao de contrato. NAO usar SUM no grao de "
               "alocacao (infla ~4x); deduplique por ContratoId para total de contratos."
           )),
)


# ============================================================
# CTE template — JOINs canonicos, LLM nunca altera
# ============================================================

CTE = """
SELECT pec.Id AS AlocacaoId,
       pec.DataInicio AS DataInicio,
       pec.DataFim AS DataFim,
       pec.Valor AS HorasContratadas,
       pec.Custo AS custo_alocacao,
       pec.CustoTechLead AS custo_tech_lead,
       pec.CustoDeliveryManager AS custo_delivery_manager,
       col.NomeCompleto AS colaborador,
       col.Email AS colaborador_email,
       dm.NomeCompleto AS delivery_manager,
       tl.NomeCompleto AS tech_lead,
       pec.ContratoId AS ContratoId,
       ct.DataInicio AS contrato_inicio,
       ct.DataEncerramento AS contrato_fim,
       ct.Valor AS contrato_valor,
       emp.Nome AS empresa_cliente,
       cc.Nome AS centro_custo,
       eo.Nome AS empresa_origem
FROM ProjetoEmpresaColaboradores pec
LEFT JOIN Colaboradores col   ON col.Id = pec.ColaboradorId
LEFT JOIN Colaboradores dm    ON dm.Id  = pec.ColaboradorDeliveryManagerId
LEFT JOIN Colaboradores tl    ON tl.Id  = pec.ColaboradorTechLeadId
LEFT JOIN Contratos ct        ON ct.Id  = pec.ContratoId
LEFT JOIN Empresas emp        ON emp.Id = ct.EmpresaId
LEFT JOIN EmpresaOrigens eo   ON eo.Id  = ct.EmpresaOrigemId
LEFT JOIN CentroCustos cc     ON cc.Id  = ct.CentroCustoId
WHERE ({FILTROS_PRINCIPAL})
""".strip()


# ============================================================
# Few-shot examples — calibram o LLM no estilo de resposta
# ============================================================

FEW_SHOTS = (
    FewShot(
        pergunta="Quem esta alocado no cliente Acme hoje?",
        sql='{"wheres":{"principal":"emp.Nome LIKE \'%Acme%\' AND pec.DataInicio <= GETDATE() AND (pec.DataFim IS NULL OR pec.DataFim >= GETDATE())"},'
            '"select_list":"colaborador, colaborador_email, delivery_manager, tech_lead, DataInicio, DataFim",'
            '"group_by":"","order_by":"colaborador ASC","top":500,'
            '"explicacao_curta":"Lista colaboradores com alocacao vigente no cliente Acme"}',
        explicacao="Alocacao ativa = DataInicio <= hoje E (DataFim NULL OR >= hoje). Sem agregacao.",
    ),
    FewShot(
        pergunta="Total de horas contratadas por delivery manager nas alocacoes ativas",
        sql='{"wheres":{"principal":"pec.DataInicio <= GETDATE() AND (pec.DataFim IS NULL OR pec.DataFim >= GETDATE()) AND pec.Valor <= 500"},'
            '"select_list":"delivery_manager, SUM(HorasContratadas) AS total_horas, COUNT(*) AS qtd_alocacoes",'
            '"group_by":"delivery_manager","order_by":"total_horas DESC","top":50,'
            '"explicacao_curta":"Soma horas contratadas por DM nas alocacoes vigentes (exclui linhas financeiras pec.Valor > 500)"}',
        explicacao="pec.Valor e bimodal (horas + ~15 linhas financeiras R$). Antes de SUM(HorasContratadas) filtre pec.Valor <= 500 pra nao misturar horas com valor financeiro; sem esse filtro o total fica inflado.",
    ),
    FewShot(
        pergunta="Contratos com encerramento nos proximos 60 dias",
        sql='{"wheres":{"principal":"ct.DataEncerramento BETWEEN GETDATE() AND DATEADD(day,60,GETDATE())"},'
            '"select_list":"empresa_cliente, ContratoId, contrato_inicio, contrato_fim, contrato_valor, colaborador",'
            '"group_by":"","order_by":"contrato_fim ASC","top":200,'
            '"explicacao_curta":"Lista contratos que encerram em ate 60 dias com colaborador alocado"}',
        explicacao="Filtro de janela em ct.DataEncerramento. Ordena por contrato_fim ASC.",
    ),
    FewShot(
        pergunta="Valor total de contratos ativos por cliente (sem inflar pelo numero de alocacoes)",
        sql='{"wheres":{"principal":"ct.IsAtivo = 1"},'
            '"select_list":"empresa_cliente, COUNT(DISTINCT ContratoId) AS qtd_contratos, SUM(DISTINCT_CONTRATO_VALOR) AS valor_total",'
            '"group_by":"empresa_cliente","order_by":"valor_total DESC","top":50,'
            '"explicacao_curta":"Valor de contratos por cliente deduplicado por ContratoId — NUNCA SUM(contrato_valor) cru no grao de alocacao"}',
        explicacao="ATENCAO: o CTE esta no grao de alocacao (~4 por contrato). SUM(contrato_valor) cru multiplica o valor ~4x. Some o valor do contrato uma vez por ContratoId (subconsulta/CTE deduplicada por ContratoId) ou agregue direto de Contratos; aqui SUM(DISTINCT_CONTRATO_VALOR) e um placeholder pra deixar claro que o valor deve ser deduplicado por contrato.",
    ),
    FewShot(
        pergunta="Capacidade ociosa: colaboradores ativos sem alocacao vigente",
        sql='{"wheres":{"principal":"col.Ativo = 1 AND NOT EXISTS (SELECT 1 FROM ProjetoEmpresaColaboradores pec2 WHERE pec2.ColaboradorId = col.Id AND pec2.DataInicio <= GETDATE() AND (pec2.DataFim IS NULL OR pec2.DataFim >= GETDATE()))"},'
            '"select_list":"DISTINCT colaborador, colaborador_email","group_by":"","order_by":"colaborador ASC","top":500,'
            '"explicacao_curta":"Colaboradores ativos que nao constam em nenhuma alocacao vigente"}',
        explicacao="NOT EXISTS subconsulta na propria tabela com alias diferente (pec2). DISTINCT pra dedupe.",
    ),
)


# ============================================================
# Dominio cravado
# ============================================================

CR_DELIVERY = registrar(Dominio(
    nome="CR_DELIVERY",
    descricao=(
        "Delivery / alocacao de colaboradores em projetos: quem esta em qual cliente, "
        "vigencia da alocacao, horas contratadas, custo da alocacao, Delivery Manager, Tech Lead, contrato vinculado, "
        "valor do contrato (no grao de contrato — nao somar cego pois o CTE esta no grao de alocacao), "
        "centro de custo, empresa origem, capacidade ociosa. "
        "Use quando a pergunta envolver projeto, alocacao, contrato, cliente do delivery, "
        "timesheet, horas, custo, margem, billable, capacidade, ociosa, delivery, tech lead, manager, vigencia. "
        "NAO use para faturamento/custo POR COLABORADOR por mes/ano (isso e CR_FOLHA_PESSOAS, tabela Folhas) — "
        "aqui o valor e do contrato inteiro, nao do quanto cada pessoa fatura/custa."
    ),
    palavras_chave=(
        "projeto, alocacao, contrato, cliente, timesheet, horas, billable, "
        "capacidade, ociosa, delivery, tech lead, manager, vigencia"
    ),
    base_conexao="cr",
    permissoes_necessarias=("delivery",),
    cte_template=CTE,
    cte_alias="delivery",
    tabelas_whitelist=(
        "ProjetoEmpresaColaboradores", "Contratos", "Colaboradores",
        "Empresas", "EmpresaOrigens", "CentroCustos",
    ),
    ramos=(
        Ramo(
            nome="principal", placeholder="FILTROS_PRINCIPAL",
            descricao="Alocacoes em ProjetoEmpresaColaboradores com colaborador + contrato + cliente.",
            colunas_filtraveis=FILTROS_PRINCIPAL,
        ),
    ),
    colunas_resultado=(
        COL_ALOCACAO_ID, COL_DATA_INICIO, COL_DATA_FIM, COL_HORAS_CONTRATADAS,
        COL_CUSTO_ALOCACAO, COL_CUSTO_TECH_LEAD, COL_CUSTO_DELIVERY_MANAGER,
        COL_COLABORADOR, COL_COLABORADOR_EMAIL, COL_DELIVERY_MANAGER, COL_TECH_LEAD,
        COL_CONTRATO_ID, COL_CONTRATO_INICIO, COL_CONTRATO_FIM, COL_CONTRATO_VALOR,
        COL_EMPRESA_CLIENTE, COL_CENTRO_CUSTO, COL_EMPRESA_ORIGEM,
    ),
    few_shots=FEW_SHOTS,
    rules="""
- Tabela mae = ProjetoEmpresaColaboradores (pec). Cada linha = uma alocacao colaborador<->contrato (grao de ALOCACAO).
- Alocacao ativa/vigente = pec.DataInicio <= GETDATE() AND (pec.DataFim IS NULL OR pec.DataFim >= GETDATE()).
- pec.Ativo (bit) tambem existe, mas DataInicio/DataFim sao o sinal canonico de vigencia. Use as datas.
- pec.Valor (HorasContratadas) e BIMODAL/mista: na MAIORIA das linhas sao HORAS mensais contratadas (tipicamente 0-250), mas ~15 linhas guardam um VALOR FINANCEIRO (R$) que coincide com contrato_valor. Valores acima de ~500 provavelmente sao financeiros. NAO faca SUM(HorasContratadas) cego — filtre (ex.: pec.Valor <= 500) ou avise o usuario, senao mistura horas + R$ e o total fica sem sentido.
- ct.Valor (Contratos.Valor / contrato_valor) e o valor financeiro do contrato e esta no GRAO DE CONTRATO. O CTE esta no grao de ALOCACAO (~4 alocacoes por contrato), entao NUNCA use SUM(contrato_valor) direto: ele multiplica o valor pelo numero de alocacoes (infla ~4x). Para valor total de contratos deduplique por ContratoId (subconsulta/CTE deduplicada por ContratoId) ou agregue a partir de Contratos. contrato_valor NAO e agregavel direto.
- custo_alocacao (pec.Custo, money) = custo mensal do colaborador na alocacao; custo_tech_lead (pec.CustoTechLead) e custo_delivery_manager (pec.CustoDeliveryManager) sao custos do TL/DM. Use-os para custo/margem do delivery (margem ~ contrato_valor - custo, atento ao grao). NUNCA use pec.Valor como custo — pec.Valor sao horas (vide acima).
- empresa_origem (eo.Nome via ct.EmpresaOrigemId) ja esta no SELECT do CTE: pode ser usada em SELECT/GROUP BY/WHERE simetrica a centro_custo.
- Colaboradores aparece 3x: principal (col), Delivery Manager (dm), Tech Lead (tl) — sempre LEFT JOIN distintos.
- Cliente do delivery = Empresas.Nome via Contratos.EmpresaId. Nao confundir com Clients (CRM).
- Contrato vigente = ct.IsAtivo = 1 OU ct.DataEncerramento IS NULL OR ct.DataEncerramento >= GETDATE().
- Capacidade ociosa = colaborador Ativo=1 SEM alocacao vigente (NOT EXISTS na propria pec). LIMITACAO: como a tabela-mae do CTE e pec, um colaborador ativo que NUNCA teve nenhuma linha de alocacao em pec nao aparece no resultado (fica invisivel). Hoje todos os ativos tem >=1 alocacao, mas idealmente capacidade ociosa partiria de Colaboradores (LEFT JOIN/NOT EXISTS), nao do CTE de alocacoes.
- Sempre que filtrar por DataFim NULL trate como "sem fim definido" (vigente).
""".strip(),
))
