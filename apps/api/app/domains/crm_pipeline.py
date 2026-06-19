"""CRM_PIPELINE — funil comercial (pré-leads + leads).

VOCABULÁRIO REAL DO CRM PROVER (confirmado pelo cliente — NÃO inverter):
- "PRÉ-LEAD" (prelead) = registro em PreLeads (cru, topo do funil, antes de virar oportunidade).
- "LEAD" = registro em Clients (a oportunidade no funil ativo: Prospecção → Conclusão).
  Também chamado de "cliente" no dia a dia. Um lead GANHO (motivo 'Contrato Assinado') é o
  "cliente fechado / venda".
Ou seja: a tabela Clients NÃO é "cliente fechado" — é o LEAD/oportunidade no funil.

Abordagem híbrida (C): CTE fixa com JOINs canônicos; LLM compõe SELECT/WHERE/GROUP BY/ORDER BY.

Schema real (validado contra CRM_colunas.tsv):
- PreLeads (pré-lead): Id, UsuarioId→AspNetUsers, StatusPreLeadId→StatusPreLeads, NomeEmpresa,
  NomeContato, EmailContato, Telefone, DtCriacao. NÃO tem área de atuação.
- Clients (lead): Id, UsuarioId→AspNetUsers, AreaAtuacaoID→AreaAtuacaos, FaseVendaID→FaseVendas,
  MotivoConclusaoVendaID→MotivoConclusaoVendas, RazaoSocial, NameClient, Email, Telefone, Creationdate.
- Lookups (StatusPreLeads, AreaAtuacaos, FaseVendas, MotivoConclusaoVendas) usam coluna `Descricao`.
- AspNetUsers: Id, Email, UserName, Nome.

Referência: Docs/APOLO_DISCOVERY/01-CRM-discovery.md
"""
from app.domains import registrar
from app.domains._base import Dominio, Ramo, Coluna, FewShot


# ============================================================
# Colunas do resultado (saída do CTE) — LLM escolhe daqui no SELECT
# ============================================================

COL_TIPO = Coluna(
    alias="tipo", expr="tipo", tipo="enum",
    descricao="Origem: 'prelead' (PreLeads, cru) ou 'lead' (Clients, oportunidade no funil = o que se chama 'lead'/'cliente').",
    nullable=False, dimensao=True, enum_valores=("prelead", "lead"),
)
COL_ID = Coluna(
    alias="id", expr="id", tipo="str",
    descricao="Id (uniqueidentifier) da entidade (PreLeads.Id ou Clients.Id, conforme tipo).",
    nullable=False,
)
COL_NOME = Coluna(
    alias="nome", expr="nome", tipo="str",
    descricao="Nome da empresa: PreLeads.NomeEmpresa (pré-lead) ou Clients.RazaoSocial (lead).",
)
COL_EMAIL = Coluna(
    alias="email", expr="email", tipo="str",
    descricao="E-mail do pré-lead (PreLeads.EmailContato) ou do lead. No lead, Clients.Email é quase sempre vazio, então cai automaticamente para o e-mail do contato em ClientContacts. Para listar todos os contatos use CRM_CONTATOS.",
)
COL_TELEFONE = Coluna(
    alias="telefone", expr="telefone", tipo="str",
    descricao="Telefone do pré-lead ou do lead. No lead, cai automaticamente para o telefone do contato (ClientContacts) quando Clients.Telefone está vazio.",
)
COL_DATA_CADASTRO = Coluna(
    alias="data_cadastro", expr="data_cadastro", tipo="datetime",
    descricao="Data de cadastro: PreLeads.DtCriacao (pré-lead) ou Clients.Creationdate (lead). 'lead cadastrado hoje' usa Clients.Creationdate.",
    dimensao=True,
)
COL_STATUS = Coluna(
    alias="status", expr="status", tipo="enum",
    descricao="Status do PRÉ-LEAD (StatusPreLeads.Descricao; só tipo='prelead', null no lead). VALORES REAIS: Desativado, Pendente, Lead, Cadastrado, Bloqueado.",
    dimensao=True, enum_valores=("Desativado", "Pendente", "Lead", "Cadastrado", "Bloqueado"),
)
COL_FASE_VENDA = Coluna(
    alias="fase_venda", expr="fase_venda", tipo="enum",
    descricao="Fase do LEAD no funil (FaseVendas.Descricao; só tipo='lead'). VALORES REAIS: Prospecção, Primeira Reunião, Reunião Técnica, Proposta, Negociação, Conclusão.",
    dimensao=True, enum_valores=("Prospecção", "Primeira Reunião", "Reunião Técnica", "Proposta", "Negociação", "Conclusão"),
)
COL_MOTIVO_CONCLUSAO = Coluna(
    alias="motivo_conclusao", expr="motivo_conclusao", tipo="str",
    descricao="Motivo de conclusão do LEAD (MotivoConclusaoVendas.Descricao; lookup fixo). GANHO/FECHADO = exatamente 'Contrato Assinado' (único de ganho); os outros ~11 são perda/desistência. Null = sem conclusão.",
    dimensao=True,
)
COL_AREA_ATUACAO = Coluna(
    alias="area_atuacao", expr="area_atuacao", tipo="str",
    descricao="Área de atuação (AreaAtuacaos.Descricao). SÓ existe no LEAD (Clients) — null para pré-lead.",
    dimensao=True,
)
COL_VENDEDOR_EMAIL = Coluna(
    alias="vendedor_email", expr="vendedor_email", tipo="str",
    descricao="E-mail do vendedor responsável (AspNetUsers.Email).",
    dimensao=True,
)
COL_VENDEDOR_NOME = Coluna(
    alias="vendedor_nome", expr="vendedor_nome", tipo="str",
    descricao="Nome do vendedor (AspNetUsers.Nome).",
    dimensao=True,
)


# ============================================================
# Colunas filtráveis dos ramos — LLM usa aqui pra montar WHERE
# ============================================================

FILTROS_PRELEAD = (
    Coluna(alias="vendedor_email", expr="u.Email", tipo="str", descricao="E-mail do vendedor do pré-lead."),
    Coluna(alias="vendedor_nome", expr="u.Nome", tipo="str", descricao="Nome do vendedor. Use LIKE '%nome%'."),
    Coluna(alias="status", expr="s.Descricao", tipo="str", descricao="Status do pré-lead (StatusPreLeads). Valores reais: Desativado, Pendente, Lead, Cadastrado, Bloqueado."),
    Coluna(alias="data_cadastro", expr="p.DtCriacao", tipo="datetime",
           descricao="Data de criação do pré-lead. Use >=, <=, BETWEEN, DATEADD."),
    Coluna(alias="nome", expr="p.NomeEmpresa", tipo="str", descricao="Nome da empresa do pré-lead. LIKE '%texto%'."),
    Coluna(alias="nome_contato", expr="p.NomeContato", tipo="str", descricao="Nome do contato no pré-lead. LIKE '%texto%'."),
    Coluna(alias="email", expr="p.EmailContato", tipo="str", descricao="E-mail de contato do pré-lead."),
)

FILTROS_LEAD = (
    Coluna(alias="vendedor_email", expr="u.Email", tipo="str", descricao="E-mail do vendedor responsável pelo lead."),
    Coluna(alias="vendedor_nome", expr="u.Nome", tipo="str", descricao="Nome do vendedor. Use LIKE '%nome%'."),
    Coluna(alias="fase_venda", expr="fv.Descricao", tipo="str", descricao="Fase do lead no funil (FaseVendas). Valores reais: Prospecção, Primeira Reunião, Reunião Técnica, Proposta, Negociação, Conclusão."),
    Coluna(alias="motivo_conclusao", expr="mc.Descricao", tipo="str",
           descricao="Motivo de ganho/perda (MotivoConclusaoVendas). ='Contrato Assinado' => lead FECHADO/GANHO (= cliente fechado/venda). Para fechados/vendas/ganhos filtre \"mc.Descricao = 'Contrato Assinado'\"."),
    Coluna(alias="area_atuacao", expr="a.Descricao", tipo="str", descricao="Área de atuação do lead (lookup AreaAtuacaos)."),
    Coluna(alias="data_cadastro", expr="c.Creationdate", tipo="datetime",
           descricao="Data de cadastro do lead (Clients.Creationdate). 'lead cadastrado hoje' = CAST(c.Creationdate AS DATE)=CAST(GETDATE() AS DATE). Use >=, <=, BETWEEN, DATEADD."),
    Coluna(alias="nome", expr="c.RazaoSocial", tipo="str", descricao="Razão social do lead/empresa. Use LIKE '%texto%'."),
    Coluna(alias="email", expr="c.Email", tipo="str", descricao="E-mail do lead (Clients.Email — quase sempre null; contato real em CRM_CONTATOS)."),
)


# ============================================================
# CTE template — JOINs canônicos, LLM nunca altera
# ============================================================

CTE = """
SELECT 'prelead' AS tipo, p.Id AS id, p.NomeEmpresa AS nome, p.EmailContato AS email, p.Telefone AS telefone,
       p.DtCriacao AS data_cadastro, s.Descricao AS status,
       NULL AS fase_venda, NULL AS motivo_conclusao,
       NULL AS area_atuacao, u.Email AS vendedor_email, u.Nome AS vendedor_nome
FROM PreLeads p
LEFT JOIN StatusPreLeads s ON s.Id = p.StatusPreLeadId
LEFT JOIN AspNetUsers u    ON u.Id = p.UsuarioId
WHERE ({FILTROS_PRELEAD})

UNION ALL

SELECT 'lead' AS tipo, c.Id AS id, c.RazaoSocial AS nome,
       COALESCE(NULLIF(LTRIM(RTRIM(c.Email)),''), (SELECT TOP 1 ccp.Email FROM ClientContacts ccp WHERE ccp.ClientID = c.Id AND ccp.Email IS NOT NULL AND LTRIM(RTRIM(ccp.Email)) <> '')) AS email,
       COALESCE(NULLIF(LTRIM(RTRIM(c.Telefone)),''), (SELECT TOP 1 ccp.Telephone FROM ClientContacts ccp WHERE ccp.ClientID = c.Id AND ccp.Telephone IS NOT NULL AND LTRIM(RTRIM(ccp.Telephone)) <> '')) AS telefone,
       c.Creationdate AS data_cadastro, NULL AS status,
       fv.Descricao AS fase_venda, mc.Descricao AS motivo_conclusao,
       a.Descricao AS area_atuacao, u.Email AS vendedor_email, u.Nome AS vendedor_nome
FROM Clients c
LEFT JOIN FaseVendas fv            ON fv.Id = c.FaseVendaID
LEFT JOIN MotivoConclusaoVendas mc ON mc.Id = c.MotivoConclusaoVendaID
LEFT JOIN AreaAtuacaos a           ON a.Id = c.AreaAtuacaoID
LEFT JOIN AspNetUsers u            ON u.Id = c.UsuarioId
WHERE ({FILTROS_LEAD})
""".strip()


# ============================================================
# Few-shot examples — calibram o LLM no estilo de resposta
# ============================================================

FEW_SHOTS = (
    FewShot(
        pergunta="Quantos leads foram cadastrados hoje e por qual vendedor?",
        sql='{"wheres":{"prelead":"1=0","lead":"CAST(c.Creationdate AS DATE) = CAST(GETDATE() AS DATE)"},'
            '"select_list":"vendedor_nome, COUNT(*) AS total","group_by":"vendedor_nome","order_by":"total DESC","top":50,'
            '"explicacao_curta":"Leads (Clients) cadastrados hoje por vendedor"}',
        explicacao="LEAD = Clients. 'cadastrado hoje' = c.Creationdate hoje. Pré-lead excluído com 1=0. (Ex: Diego cadastrar um lead hoje aparece AQUI.)",
    ),
    FewShot(
        pergunta="O vendedor Diego da Costa Afonso cadastrou quantos leads hoje?",
        sql='{"wheres":{"prelead":"1=0","lead":"u.Nome LIKE \'%Diego da Costa Afonso%\' AND CAST(c.Creationdate AS DATE) = CAST(GETDATE() AS DATE)"},'
            '"select_list":"COUNT(*) AS total","group_by":"","order_by":"","top":1,'
            '"explicacao_curta":"Leads (Clients) do Diego cadastrados hoje"}',
        explicacao="'leads cadastrados' = ramo lead (Clients), filtra vendedor por u.Nome e data por c.Creationdate. Pré-lead = 1=0.",
    ),
    FewShot(
        pergunta="Leads em fase Proposta ha mais de 30 dias",
        sql='{"wheres":{"prelead":"1=0","lead":"fv.Descricao = \'Proposta\' AND c.Creationdate <= DATEADD(day,-30,GETDATE())"},'
            '"select_list":"nome, vendedor_nome, fase_venda, data_cadastro","group_by":"","order_by":"data_cadastro ASC","top":500,'
            '"explicacao_curta":"Leads na fase Proposta há mais de 30 dias"}',
        explicacao="LEAD (Clients) tem fase de venda. fv.Descricao='Proposta'. Pré-lead excluído.",
    ),
    FewShot(
        pergunta="Quantos leads foram fechados (venda) este ano?",
        sql='{"wheres":{"prelead":"1=0","lead":"mc.Descricao = \'Contrato Assinado\' AND YEAR(c.Creationdate) = YEAR(GETDATE())"},'
            '"select_list":"COUNT(*) AS total","group_by":"","order_by":"","top":1,'
            '"explicacao_curta":"Leads ganhos (Contrato Assinado) no ano atual"}',
        explicacao="FECHADO/VENDA = lead com mc.Descricao='Contrato Assinado'. NÃO contar toda a tabela Clients (são oportunidades em aberto).",
    ),
    FewShot(
        pergunta="Qual vendedor mais vendeu em 2025?",
        sql='{"wheres":{"prelead":"1=0","lead":"mc.Descricao = \'Contrato Assinado\' AND YEAR(c.Creationdate) = 2025"},'
            '"select_list":"vendedor_nome, COUNT(*) AS total_vendas","group_by":"vendedor_nome","order_by":"total_vendas DESC","top":10,'
            '"explicacao_curta":"Ranking de vendedores por leads ganhos (Contrato Assinado) em 2025"}',
        explicacao="VENDEU/GANHOU = mc.Descricao='Contrato Assinado'. Mesmo com 'quem mais', TOP 10 pra dar o ranking.",
    ),
    FewShot(
        pergunta="Quantos pre-leads parados ha mais de 30 dias por vendedor",
        sql='{"wheres":{"prelead":"p.DtCriacao <= DATEADD(day,-30,GETDATE())","lead":"1=0"},'
            '"select_list":"vendedor_nome, COUNT(*) AS total","group_by":"vendedor_nome","order_by":"total DESC","top":10,'
            '"explicacao_curta":"Pré-leads (PreLeads) parados há mais de 30 dias por vendedor"}',
        explicacao="PRÉ-LEAD = PreLeads. Use o ramo prelead (p.DtCriacao). Lead excluído com 1=0.",
    ),
)


# ============================================================
# Dominio cravado
# ============================================================

CRM_PIPELINE = registrar(Dominio(
    nome="CRM_PIPELINE",
    descricao=(
        "Funil comercial do CRM. VOCABULÁRIO: 'LEAD' = registro em Clients (a oportunidade no funil "
        "ativo — Prospecção, Primeira Reunião, Negociação, Conclusão); 'PRÉ-LEAD' = registro em PreLeads "
        "(cru, antes de virar lead). 'cliente' = também o lead (Clients). 'FECHADO/GANHO/VENDA/cliente fechado' "
        "= lead com motivo 'Contrato Assinado'. "
        "Use para: lead/cliente/pré-lead, leads cadastrados (hoje/no período), fase de venda, ganho/perda, "
        "fechados/vendas, área de atuação, status do pré-lead, ranking de vendedores por vendas. "
        "VENDEDOR que mais faturou/vendeu/fechou/ganhou = AQUI (vendas), NUNCA folha de pagamento. "
        "Para TELEFONE/E-MAIL/contato de um cliente, use CRM_CONTATOS (aqui Clients.Email é quase sempre vazio)."
    ),
    palavras_chave=(
        "lead, leads, cliente, clientes, client, prelead, pre-lead, pré-lead, funil, pipeline, fase, "
        "faseventa, conversao, ganho, perdido, fechado, fechamos, contrato assinado, motivo, area, "
        "vendedor, status, prospeccao, vendeu, venda, vendas, cadastrou, cadastrado, cadastrados"
    ),
    base_conexao="crm",
    permissoes_necessarias=(),
    cte_template=CTE,
    cte_alias="pipeline",
    tabelas_whitelist=(
        "PreLeads", "Clients", "StatusPreLeads", "AspNetUsers",
        "AreaAtuacaos", "FaseVendas", "MotivoConclusaoVendas", "ClientContacts",
    ),
    ramos=(
        Ramo(
            nome="prelead", placeholder="FILTROS_PRELEAD",
            descricao="Registros da tabela PreLeads (pré-lead cru, antes de virar lead).",
            colunas_filtraveis=FILTROS_PRELEAD,
        ),
        Ramo(
            nome="lead", placeholder="FILTROS_LEAD",
            descricao="Registros da tabela Clients (o LEAD / oportunidade no funil; também chamado de cliente).",
            colunas_filtraveis=FILTROS_LEAD,
        ),
    ),
    colunas_resultado=(
        COL_TIPO, COL_ID, COL_NOME, COL_EMAIL, COL_TELEFONE,
        COL_DATA_CADASTRO, COL_STATUS, COL_FASE_VENDA, COL_MOTIVO_CONCLUSAO,
        COL_AREA_ATUACAO, COL_VENDEDOR_EMAIL, COL_VENDEDOR_NOME,
    ),
    few_shots=FEW_SHOTS,
    rules="""
- VOCABULÁRIO (CRAVADO, não inverter):
  * "LEAD" / "cliente" = registro em Clients (oportunidade no funil ativo). Use o ramo 'lead'.
  * "PRÉ-LEAD" / "prelead" = registro em PreLeads (cru). Use o ramo 'prelead'. Só quando disserem explicitamente "pré-lead".
  * Quando o usuário disser apenas "lead" ou "cliente", é o ramo 'lead' (Clients), NÃO PreLeads.
- "lead cadastrado hoje / X cadastrou N leads hoje / leads cadastrados no período" = ramo lead (Clients) por
  c.Creationdate (prelead = "1=0"). Ex.: um lead novo do vendedor Diego cadastrado hoje aparece no ramo lead.
- "FECHADO / GANHO / VENDA / VENDEU / contrato assinado / cliente fechado / fechamos" = lead cujo
  motivo_conclusao = 'Contrato Assinado': filtre `mc.Descricao = 'Contrato Assinado'`. NUNCA conte toda a
  tabela Clients como fechados (a maioria está em Prospecção/Primeira Reunião). Ano via YEAR(c.Creationdate).
- "Vendedor que mais vendeu/fechou" = COUNT de leads com mc.Descricao='Contrato Assinado' por vendedor (prelead="1=0").
- "Quantos leads" (genérico, sem 'fechado') = COUNT do ramo lead (Clients), prelead="1=0".
- "PERDIDO" = lead com motivo_conclusao != 'Contrato Assinado' (ex: 'Seguiu com outra empresa').
- fase de venda (só lead): Prospecção, Primeira Reunião, Reunião Técnica, Proposta, Negociação, Conclusão.
- status (só pré-lead): Desativado, Pendente, Lead, Cadastrado, Bloqueado.
- Só pré-leads: prelead=filtros, lead="1=0". Só leads: prelead="1=0", lead=filtros.
- ÁREA DE ATUAÇÃO só existe no lead (Clients); null no pré-lead — nunca agrupe pré-lead por área.
- TELEFONE/E-MAIL/contato de um cliente: o e-mail (Clients.Email) e telefone aqui são quase sempre NULL.
  Para contato real (pessoa, e-mail, telefone) o domínio certo é CRM_CONTATOS (tabela ClientContacts).
- Vendedor por AspNetUsers.Email (vendedor_email) e AspNetUsers.Nome (vendedor_nome — filtrar nome por LIKE).
- Datas: pré-lead=PreLeads.DtCriacao; lead=Clients.Creationdate. Não há data confiável de fechamento.
- "em 2025": YEAR(coluna)=2025. "ano passado": YEAR(coluna)=YEAR(GETDATE())-1. "hoje": CAST(coluna AS DATE)=CAST(GETDATE() AS DATE).
""".strip(),
))
