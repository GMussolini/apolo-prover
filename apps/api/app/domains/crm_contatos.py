"""CRM_CONTATOS — diretório de contatos (pessoas) das empresas-cliente.

Os contatos reais (nome, e-mail, telefone, cargo) vivem em ClientContacts (1.905 linhas) —
NÃO em Clients.Email/Telefone, que estão quase sempre vazios. Este domínio expõe esse
diretório para perguntas tipo "qual o contato/telefone/e-mail do cliente X".

Schema (validado contra CRM_colunas.tsv):
- ClientContacts: Id, ClientID→Clients, Name, Email, Telephone, JobCompanyClient,
  Departamento, Linkedin, Colaborador (bit), DecisionLevel (int), UltimoContato.
  Colunas de identidade em INGLÊS: Name / Email / Telephone.
- Clients: Id, RazaoSocial, NameClient, UsuarioId→AspNetUsers.
- AspNetUsers: Id, Nome, Email.
"""
from app.domains import registrar
from app.domains._base import Dominio, Ramo, Coluna, FewShot


# ============================================================
# Colunas do resultado (saída do CTE)
# ============================================================

COL_CONTATO_ID = Coluna(
    alias="contato_id", expr="contato_id", tipo="str",
    descricao="Id do contato (ClientContacts.Id).", nullable=False,
)
COL_CONTATO_NOME = Coluna(
    alias="contato_nome", expr="contato_nome", tipo="str",
    descricao="Nome da PESSOA de contato (ClientContacts.Name — coluna em inglês 'Name').",
    dimensao=True,
)
COL_CONTATO_EMAIL = Coluna(
    alias="contato_email", expr="contato_email", tipo="str",
    descricao="E-mail do contato (ClientContacts.Email). É AQUI que mora o e-mail real do cliente, não em Clients.Email.",
)
COL_CONTATO_TELEFONE = Coluna(
    alias="contato_telefone", expr="contato_telefone", tipo="str",
    descricao="Telefone do contato (ClientContacts.Telephone — coluna em inglês 'Telephone').",
)
COL_CARGO = Coluna(
    alias="cargo", expr="cargo", tipo="str",
    descricao="Cargo/função do contato na empresa-cliente (ClientContacts.JobCompanyClient).",
    dimensao=True,
)
COL_DEPARTAMENTO = Coluna(
    alias="departamento", expr="departamento", tipo="str",
    descricao="Departamento do contato (ClientContacts.Departamento).", dimensao=True,
)
COL_LINKEDIN = Coluna(
    alias="linkedin", expr="linkedin", tipo="str",
    descricao="LinkedIn do contato (ClientContacts.Linkedin).",
)
COL_ULTIMO_CONTATO = Coluna(
    alias="ultimo_contato", expr="ultimo_contato", tipo="datetime",
    descricao="Data/hora do último contato registrado com a pessoa (ClientContacts.UltimoContato).",
    dimensao=True,
)
COL_CONTATO_INTERNO = Coluna(
    alias="contato_interno", expr="contato_interno", tipo="int",
    descricao="1 = contato é colaborador interno (Prover); 0 = contato externo do cliente. (ClientContacts.Colaborador).",
    dimensao=True, enum_valores=("0", "1"),
)
COL_EMPRESA_CLIENTE = Coluna(
    alias="empresa_cliente", expr="empresa_cliente", tipo="str",
    descricao="Empresa-cliente a que o contato pertence (Clients.RazaoSocial via cc.ClientID).",
    dimensao=True,
)
COL_VENDEDOR_NOME = Coluna(
    alias="vendedor_nome", expr="vendedor_nome", tipo="str",
    descricao="Nome do vendedor responsável pela empresa-cliente (AspNetUsers.Nome).", dimensao=True,
)
COL_VENDEDOR_EMAIL = Coluna(
    alias="vendedor_email", expr="vendedor_email", tipo="str",
    descricao="E-mail do vendedor responsável (AspNetUsers.Email).", dimensao=True,
)


# ============================================================
# Colunas filtráveis
# ============================================================

FILTROS_PRINCIPAL = (
    Coluna(alias="contato_nome", expr="cc.Name", tipo="str", descricao="Nome do contato (pessoa). Use LIKE '%texto%'."),
    Coluna(alias="contato_email", expr="cc.Email", tipo="str", descricao="E-mail do contato. Use LIKE '%texto%'."),
    Coluna(alias="contato_telefone", expr="cc.Telephone", tipo="str", descricao="Telefone do contato."),
    Coluna(alias="cargo", expr="cc.JobCompanyClient", tipo="str", descricao="Cargo do contato. Use LIKE '%texto%'."),
    Coluna(alias="departamento", expr="cc.Departamento", tipo="str", descricao="Departamento do contato."),
    Coluna(alias="empresa_cliente", expr="c.RazaoSocial", tipo="str",
           descricao="Empresa-cliente do contato (Clients.RazaoSocial). 'Contatos do cliente X' => c.RazaoSocial LIKE '%X%'."),
    Coluna(alias="empresa_fantasia", expr="c.NameClient", tipo="str", descricao="Nome fantasia do cliente."),
    Coluna(alias="vendedor_nome", expr="u.Nome", tipo="str", descricao="Nome do vendedor responsável. Use LIKE '%texto%'."),
    Coluna(alias="vendedor_email", expr="u.Email", tipo="str", descricao="E-mail do vendedor responsável."),
    Coluna(alias="contato_interno", expr="cc.Colaborador", tipo="int",
           descricao="1 = contato interno (Prover), 0 = externo do cliente. Para 'contatos do cliente' use = 0."),
    Coluna(alias="ultimo_contato", expr="cc.UltimoContato", tipo="datetime",
           descricao="Data do último contato. Use comparadores >=, <=, DATEADD para 'sem contato há N dias'."),
    Coluna(alias="decisor", expr="cc.DecisionLevel", tipo="int",
           descricao="Nível de decisão do contato (int; maior = mais decisor). Use comparadores."),
)


# ============================================================
# CTE template
# ============================================================

CTE = """
SELECT cc.Id              AS contato_id,
       cc.Name            AS contato_nome,
       cc.Email           AS contato_email,
       cc.Telephone       AS contato_telefone,
       cc.JobCompanyClient AS cargo,
       cc.Departamento    AS departamento,
       cc.Linkedin        AS linkedin,
       cc.UltimoContato   AS ultimo_contato,
       cc.Colaborador     AS contato_interno,
       c.RazaoSocial      AS empresa_cliente,
       u.Nome             AS vendedor_nome,
       u.Email            AS vendedor_email
FROM ClientContacts cc
LEFT JOIN Clients c     ON c.Id = cc.ClientID
LEFT JOIN AspNetUsers u ON u.Id = c.UsuarioId
WHERE ({FILTROS_PRINCIPAL})
""".strip()


# ============================================================
# Few-shots
# ============================================================

FEW_SHOTS = (
    FewShot(
        pergunta="Qual o contato do cliente Global Drones?",
        sql='{"wheres":{"principal":"c.RazaoSocial LIKE \'%Global Drones%\'"},'
            '"select_list":"contato_nome, cargo, contato_email, contato_telefone","group_by":"","order_by":"","top":50,'
            '"explicacao_curta":"Lista os contatos (pessoas) da empresa-cliente Global Drones"}',
        explicacao="Filtra pela empresa-cliente (c.RazaoSocial LIKE). Traz nome/cargo/email/telefone do contato.",
    ),
    FewShot(
        pergunta="Quantos contatos cada cliente tem?",
        sql='{"wheres":{"principal":"cc.Colaborador = 0"},'
            '"select_list":"empresa_cliente, COUNT(*) AS qtd_contatos","group_by":"empresa_cliente","order_by":"qtd_contatos DESC","top":500,'
            '"explicacao_curta":"Conta contatos externos por empresa-cliente"}',
        explicacao="GROUP BY empresa_cliente. Colaborador=0 isola contatos externos do cliente.",
    ),
    FewShot(
        pergunta="Contatos sem retorno ha mais de 90 dias",
        sql='{"wheres":{"principal":"cc.UltimoContato < DATEADD(day,-90,GETDATE())"},'
            '"select_list":"contato_nome, empresa_cliente, cargo, ultimo_contato","group_by":"","order_by":"ultimo_contato ASC","top":500,'
            '"explicacao_curta":"Contatos cujo último contato foi há mais de 90 dias"}',
        explicacao="Filtro temporal por cc.UltimoContato. Ordena do mais antigo.",
    ),
)


# ============================================================
# Dominio cravado
# ============================================================

CRM_CONTATOS = registrar(Dominio(
    nome="CRM_CONTATOS",
    descricao=(
        "Diretório de CONTATOS (pessoas) das empresas-cliente: nome, e-mail, telefone, cargo, "
        "departamento, LinkedIn, último contato e nível de decisão. Use SEMPRE que a pergunta for "
        "sobre o CONTATO de um cliente — telefone, e-mail, com quem falar, interlocutor, pessoa de "
        "contato, decisor de uma empresa. Os contatos reais vivem em ClientContacts; Clients.Email/Telefone "
        "estão quase sempre vazios, então pergunta de contato de cliente vem AQUI, não no CRM_PIPELINE."
    ),
    palavras_chave=(
        "contato, contatos, telefone, telefones, email, e-mail, interlocutor, pessoa de contato, "
        "decisor, falar com, ligar para, quem atende, cargo do contato, linkedin, departamento do contato"
    ),
    base_conexao="crm",
    permissoes_necessarias=(),
    cte_template=CTE,
    cte_alias="contatos",
    tabelas_whitelist=("ClientContacts", "Clients", "AspNetUsers"),
    ramos=(
        Ramo(
            nome="principal", placeholder="FILTROS_PRINCIPAL",
            descricao="Contatos em ClientContacts (pessoas das empresas-cliente).",
            colunas_filtraveis=FILTROS_PRINCIPAL,
        ),
    ),
    colunas_resultado=(
        COL_CONTATO_ID, COL_CONTATO_NOME, COL_CONTATO_EMAIL, COL_CONTATO_TELEFONE,
        COL_CARGO, COL_DEPARTAMENTO, COL_LINKEDIN, COL_ULTIMO_CONTATO,
        COL_CONTATO_INTERNO, COL_EMPRESA_CLIENTE, COL_VENDEDOR_NOME, COL_VENDEDOR_EMAIL,
    ),
    few_shots=FEW_SHOTS,
    rules="""
- Tabela base = ClientContacts (pessoas de contato das empresas-cliente).
- COLUNAS DE IDENTIDADE EM INGLÊS: cc.Name (nome da pessoa), cc.Email, cc.Telephone — NÃO 'Nome'/'Telefone'.
- "telefone / e-mail / contato do cliente X" = AQUI (ClientContacts), NUNCA Clients.Email/Telefone (quase sempre null).
- Empresa-cliente = Clients.RazaoSocial via cc.ClientID. "contatos do cliente X" => c.RazaoSocial LIKE '%X%'.
- cc.Colaborador = 1 → contato INTERNO (colaborador Prover); = 0 → contato EXTERNO do cliente.
  Para "contatos do cliente" geralmente filtre cc.Colaborador = 0 (a menos que peçam internos).
- Vendedor responsável pelo cliente: AspNetUsers.Nome/Email via Clients.UsuarioId.
- "sem contato há N dias" = cc.UltimoContato < DATEADD(day,-N,GETDATE()).
- "decisores" = cc.DecisionLevel alto (int; ordene DESC).
""".strip(),
))
