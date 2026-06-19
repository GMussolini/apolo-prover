"""CRM_OPERACAO_VENDEDOR — atividade operacional dos vendedores (Tarefas + Reuniões).

Abordagem híbrida (C): CTE fixa com JOINs canônicos; LLM compõe SELECT/WHERE/GROUP BY/ORDER BY
escolhendo colunas declaradas na ontologia.

Referência: Docs/APOLO_DISCOVERY/01-CRM-discovery.md + 04-APOLO-dominios.md
"""
from app.domains import registrar
from app.domains._base import Dominio, Ramo, Coluna, FewShot


# ============================================================
# Colunas do resultado (saída do CTE) — LLM escolhe daqui no SELECT
# ============================================================

COL_TIPO = Coluna(
    alias="tipo", expr="tipo", tipo="enum",
    descricao="Origem do registro: 'tarefa' (Tarefas) ou 'reuniao' (Reunioes).",
    nullable=False, dimensao=True, enum_valores=("tarefa", "reuniao"),
)
COL_ID = Coluna(
    alias="id", expr="id", tipo="str",
    descricao="Id da entidade (Tarefas.Id ou Reunioes.Id).",
    nullable=False,
)
COL_DESCRICAO = Coluna(
    alias="descricao", expr="descricao", tipo="str",
    descricao="Descrição da tarefa ou título da reunião.",
)
COL_SUBTIPO = Coluna(
    alias="subtipo", expr="subtipo", tipo="str",
    descricao=(
        "Tipo específico. Para tarefa = TipoTarefas.Descricao; valores reais (use LIKE, não igualdade exata): "
        "'Fazer ligação (Telefone)', 'WhatsApp', 'Enviar Email', 'Evento', 'Primeira reunião', "
        "'Reunião técnica', 'Reunião de proposta', 'Envio de proposta', 'Feedback'. "
        "Para reunião = TipoReuniao.Descricao, mas é SEMPRE NULL (TipoReuniaoId não populado) — não agrupe reunião por subtipo; use status."
    ),
    dimensao=True,
)
COL_STATUS = Coluna(
    alias="status", expr="status", tipo="str",
    descricao=(
        "Status textual da reunião (Reunioes.Status): 'Realizada' (=realizada), 'Agendada', 'Cancelada'. "
        "NULL para tarefa (Tarefas não tem Status textual; use 'concluida'/'atrasada')."
    ),
    dimensao=True, enum_valores=("Agendada", "Cancelada", "Realizada"),
)
COL_DATA_AGENDAMENTO = Coluna(
    alias="data_agendamento", expr="data_agendamento", tipo="datetime",
    descricao="Data agendada: Tarefas.Data (tarefa) ou Reunioes.DataInicioAgendada (reuniao).",
    dimensao=True,
)
COL_DATA_CONCLUSAO = Coluna(
    alias="data_conclusao", expr="data_conclusao", tipo="datetime",
    descricao=(
        "Data de conclusão. Tarefa: DataExecucao SÓ quando TarefaExecutada=1 (DataExecucao vem preenchida mesmo em pendentes, então NÃO é sinal de conclusão por si só). "
        "Reunião: DataFimAgendada SÓ quando Status='Realizada'. Null = não concluída/pendente."
    ),
    dimensao=True,
)
COL_ATRASADA = Coluna(
    alias="atrasada", expr="atrasada", tipo="int",
    descricao=(
        "Flag 1/0 de atraso. Tarefa: 1 = TarefaExecutada=0 AND DtReturn < GETDATE() AND lead ATIVO (Clients.FaseAtivo=1) "
        "AND é a tarefa ATUAL do lead (não existe outra tarefa aberta com DtReturn maior p/ o mesmo cliente). "
        "Cada lead tem várias tarefas empilhadas; só a última aberta conta. Se a próxima já foi reagendada p/ o futuro, o lead NÃO está atrasado — "
        "por isso ignoramos linhas vencidas que já foram substituídas por um follow-up novo (NOT EXISTS tarefa aberta mais nova). Igual ao dashboard do CRM. "
        "(DtReturn = data de retorno/follow-up = data-limite, NÃO a Data agendada.) "
        "Reunião: 1 = Status='Agendada' AND DataInicioAgendada < GETDATE()."
    ),
    nullable=False, agregavel=True, dimensao=True, enum_valores=("0", "1"),
)
COL_CLIENTE_NOME = Coluna(
    alias="cliente_nome", expr="cliente_nome", tipo="str",
    descricao="Nome do cliente vinculado (Clients.RazaoSocial). Null em reuniões sem ClientId.",
    dimensao=True,
)
COL_CONTATO_NOME = Coluna(
    alias="contato_nome", expr="contato_nome", tipo="str",
    descricao="Nome do contato do cliente (ClientContacts.Name). Só para tarefa; null em reuniao.",
)
COL_VENDEDOR_EMAIL = Coluna(
    alias="vendedor_email", expr="vendedor_email", tipo="str",
    descricao="E-mail do vendedor responsável (AspNetUsers.Email). Em reuniões = COALESCE(AspNetUsers.Email, Reunioes.OrganizadorEmail) (fallback quando o organizador não existe em AspNetUsers).",
    dimensao=True,
)
COL_VENDEDOR_NOME = Coluna(
    alias="vendedor_nome", expr="vendedor_nome", tipo="str",
    descricao="Nome real do vendedor (AspNetUsers.Nome). Em reuniões = COALESCE(AspNetUsers.Nome, Reunioes.OrganizadorNome). UserName é login/e-mail, não use para filtrar por nome.",
    dimensao=True,
)
COL_QTD_PARTICIPANTES = Coluna(
    alias="qtd_participantes", expr="qtd_participantes", tipo="int",
    descricao="Quantidade de participantes da reunião (Reunioes.TotalParticipantes). Null em tarefa.",
    agregavel=True,
)


# ============================================================
# Colunas filtráveis dos ramos — LLM usa aqui pra montar WHERE
# ============================================================

FILTROS_TAREFA = (
    Coluna(alias="vendedor_email", expr="u.Email", tipo="str", descricao="E-mail do vendedor responsável pela tarefa."),
    Coluna(alias="vendedor_nome", expr="u.Nome", tipo="str", descricao="Nome real do vendedor (AspNetUsers.Nome). Use LIKE '%nome%'. NÃO é o UserName/login."),
    Coluna(alias="subtipo", expr="tt.Descricao", tipo="str",
           descricao=("Tipo da tarefa (TipoTarefas.Descricao). Use LIKE '%...%', NÃO igualdade exata. "
                      "Valores reais: 'Fazer ligação (Telefone)', 'WhatsApp', 'Enviar Email', 'Evento', "
                      "'Primeira reunião', 'Reunião técnica', 'Reunião de proposta', 'Envio de proposta', 'Feedback'. "
                      "Ex.: ligação -> tt.Descricao LIKE '%ligação%'; e-mail -> tt.Descricao LIKE '%Email%'. Não existe tipo 'Follow-up'.")),
    Coluna(alias="cliente_nome", expr="c.RazaoSocial", tipo="str", descricao="Nome do cliente vinculado à tarefa."),
    Coluna(alias="contato_nome", expr="cc.Name", tipo="str", descricao="Nome do contato do cliente."),
    Coluna(alias="data_agendamento", expr="t.Data", tipo="datetime",
           descricao="Data agendada da tarefa (quando foi marcada). Use >=, <=, BETWEEN."),
    Coluna(alias="data_retorno", expr="t.DtReturn", tipo="datetime",
           descricao="Data de retorno/follow-up (deadline da tarefa). É esta data que define 'atrasada'. Use >=, <=, BETWEEN, DATEADD."),
    Coluna(alias="data_conclusao", expr="(CASE WHEN t.TarefaExecutada = 1 THEN t.DataExecucao ELSE NULL END)", tipo="datetime",
           descricao="Data de execução SÓ quando TarefaExecutada=1. DataExecucao vem preenchida mesmo em pendentes, então NÃO use DataExecucao IS NULL como sinal de conclusão; use 'concluida'."),
    Coluna(alias="concluida", expr="(CASE WHEN t.TarefaExecutada = 1 THEN 1 ELSE 0 END)", tipo="int",
           descricao="1 = TarefaExecutada=1 (concluída), 0 = pendente. Sinal autoritativo de conclusão. Use '= 1' ou '= 0'."),
    Coluna(alias="atrasada",
           expr="(CASE WHEN t.TarefaExecutada = 0 AND t.DtReturn < GETDATE() AND c.FaseAtivo = 1 AND NOT EXISTS (SELECT 1 FROM Tarefas tnx WHERE tnx.ClientID = t.ClientID AND tnx.TarefaExecutada = 0 AND tnx.DtReturn > t.DtReturn) THEN 1 ELSE 0 END)",
           tipo="int",
           descricao="1 = atrasada: não executada (TarefaExecutada=0), data de retorno passou (DtReturn < hoje), lead ATIVO (Clients.FaseAtivo=1) E é a tarefa ATUAL do lead (não há outra tarefa aberta com DtReturn maior p/ o mesmo cliente). 0 = no prazo, concluída, lead inativo OU já substituída por um follow-up futuro."),
)

FILTROS_REUNIAO = (
    Coluna(alias="vendedor_email", expr="u.Email", tipo="str",
           descricao="E-mail do vendedor — match feito via AspNetUsers.Email = Reunioes.OrganizadorEmail."),
    Coluna(alias="vendedor_nome", expr="u.Nome", tipo="str", descricao="Nome real do organizador (AspNetUsers.Nome). Use LIKE '%nome%'."),
    Coluna(alias="subtipo", expr="tr.Descricao", tipo="str",
           descricao="Tipo da reunião (TipoReuniao.Descricao). LACUNA: é SEMPRE NULL (TipoReuniaoId não populado). NÃO filtre/agrupe reunião por subtipo; use 'status'."),
    Coluna(alias="cliente_nome", expr="c.RazaoSocial", tipo="str", descricao="Nome do cliente vinculado à reunião."),
    Coluna(alias="data_agendamento", expr="r.DataInicioAgendada", tipo="datetime",
           descricao="Data/hora de início agendada da reunião."),
    Coluna(alias="data_conclusao", expr="(CASE WHEN r.Status = 'Realizada' THEN r.DataFimAgendada ELSE NULL END)", tipo="datetime",
           descricao="Data/hora fim, SÓ quando Status='Realizada'. DataFimAgendada nunca é nula, então NÃO a use como sinal de conclusão; conclusão de reunião vem de Status='Realizada'."),
    Coluna(alias="status", expr="r.Status", tipo="str",
           descricao="Status textual da reunião. Valores reais: 'Realizada' (=realizada), 'Agendada', 'Cancelada'. NÃO existe 'Concluída'."),
    Coluna(alias="qtd_participantes", expr="r.TotalParticipantes", tipo="int",
           descricao="Total de participantes."),
    Coluna(alias="atrasada",
           expr="(CASE WHEN r.Status = 'Agendada' AND r.DataInicioAgendada < GETDATE() THEN 1 ELSE 0 END)",
           tipo="int",
           descricao="1 = reunião ainda 'Agendada' cujo início já passou (não realizada nem cancelada)."),
)


# ============================================================
# CTE template — JOINs canônicos, LLM nunca altera
# ============================================================

CTE = """
SELECT 'tarefa' AS tipo,
       CAST(t.Id AS NVARCHAR(50)) AS id,
       t.Descricao AS descricao,
       tt.Descricao AS subtipo,
       NULL AS status,
       t.Data AS data_agendamento,
       CASE WHEN t.TarefaExecutada = 1 THEN t.DataExecucao ELSE NULL END AS data_conclusao,
       CASE WHEN t.TarefaExecutada = 0 AND t.DtReturn < GETDATE() AND c.FaseAtivo = 1
                 AND NOT EXISTS (SELECT 1 FROM Tarefas tnx WHERE tnx.ClientID = t.ClientID AND tnx.TarefaExecutada = 0 AND tnx.DtReturn > t.DtReturn)
            THEN 1 ELSE 0 END AS atrasada,
       c.RazaoSocial AS cliente_nome,
       cc.Name AS contato_nome,
       u.Email AS vendedor_email,
       u.Nome AS vendedor_nome,
       NULL AS qtd_participantes
FROM Tarefas t
LEFT JOIN TipoTarefas tt    ON tt.Id = t.TipoTarefaID
LEFT JOIN Clients c         ON c.Id = t.ClientID
LEFT JOIN ClientContacts cc ON cc.Id = t.ClientContactId
LEFT JOIN AspNetUsers u     ON u.Id = t.UsuarioID
WHERE ({FILTROS_TAREFA})

UNION ALL

SELECT 'reuniao' AS tipo,
       CAST(r.Id AS NVARCHAR(50)) AS id,
       r.Titulo AS descricao,
       tr.Descricao AS subtipo,
       r.Status AS status,
       r.DataInicioAgendada AS data_agendamento,
       CASE WHEN r.Status = 'Realizada' THEN r.DataFimAgendada ELSE NULL END AS data_conclusao,
       CASE WHEN r.Status = 'Agendada' AND r.DataInicioAgendada < GETDATE() THEN 1 ELSE 0 END AS atrasada,
       c.RazaoSocial AS cliente_nome,
       NULL AS contato_nome,
       COALESCE(u.Email, r.OrganizadorEmail) AS vendedor_email,
       COALESCE(u.Nome, r.OrganizadorNome) AS vendedor_nome,
       r.TotalParticipantes AS qtd_participantes
FROM Reunioes r
LEFT JOIN TipoReuniao tr ON tr.Id = r.TipoReuniaoId
LEFT JOIN Clients c      ON c.Id = r.ClientId
LEFT JOIN AspNetUsers u  ON u.Email = r.OrganizadorEmail
WHERE ({FILTROS_REUNIAO})
""".strip()


# ============================================================
# Few-shot examples — calibram o LLM no estilo de resposta
# ============================================================

FEW_SHOTS = (
    FewShot(
        pergunta="Quantas tarefas atrasadas o Felipe tem?",
        sql='{"wheres":{"tarefa":"u.Email = \'foliveira@provertec.com.br\' AND t.TarefaExecutada = 0 AND t.DtReturn < GETDATE() AND c.FaseAtivo = 1 AND NOT EXISTS (SELECT 1 FROM Tarefas tnx WHERE tnx.ClientID = t.ClientID AND tnx.TarefaExecutada = 0 AND tnx.DtReturn > t.DtReturn)","reuniao":"1=0"},'
            '"select_list":"COUNT(*) AS total","group_by":"","order_by":"","top":1,'
            '"explicacao_curta":"Conta tarefas do Felipe atrasadas (não executadas e com data no passado)"}',
        explicacao="Filtro de vendedor + atraso (TarefaExecutada=0, pois DataExecucao fica preenchida mesmo em pendentes). Reunião excluída com 1=0.",
    ),
    FewShot(
        pergunta="Top 10 vendedores por reunioes realizadas nos ultimos 30 dias",
        sql='{"wheres":{"tarefa":"1=0","reuniao":"r.DataInicioAgendada >= DATEADD(day,-30,GETDATE()) AND r.Status = \'Realizada\'"},'
            '"select_list":"vendedor_email, COUNT(*) AS total","group_by":"vendedor_email","order_by":"total DESC","top":10,'
            '"explicacao_curta":"Ranking de vendedores por reuniões realizadas no último mês"}',
        explicacao="Agregação COUNT + GROUP BY por vendedor. Reunião realizada = r.Status='Realizada' (NÃO existe 'Concluída'). Tarefa excluída com 1=0. TOP 10.",
    ),
    FewShot(
        pergunta="Distribuicao de tarefas por tipo neste mes",
        sql='{"wheres":{"tarefa":"t.Data >= DATEADD(day,-30,GETDATE())","reuniao":"1=0"},'
            '"select_list":"subtipo, COUNT(*) AS total","group_by":"subtipo","order_by":"total DESC","top":500,'
            '"explicacao_curta":"Conta tarefas agrupadas por tipo (ligação/WhatsApp/e-mail/evento) nos últimos 30 dias"}',
        explicacao="GROUP BY subtipo (TipoTarefas.Descricao: 'Fazer ligação (Telefone)', 'WhatsApp', 'Enviar Email', etc.). Reunião excluída com 1=0.",
    ),
    FewShot(
        pergunta="Distribuicao de reunioes por status",
        sql='{"wheres":{"tarefa":"1=0","reuniao":"1=1"},'
            '"select_list":"status, COUNT(*) AS total","group_by":"status","order_by":"total DESC","top":500,'
            '"explicacao_curta":"Conta reuniões agrupadas por status (Realizada/Agendada/Cancelada)"}',
        explicacao="GROUP BY status (Reunioes.Status). Use status, não subtipo, que é sempre nulo em reuniões. Tarefa excluída com 1=0.",
    ),
    FewShot(
        pergunta="Reunioes com mais de 5 participantes do vendedor wsoares",
        sql='{"wheres":{"tarefa":"1=0","reuniao":"u.Email = \'wsoares@provertec.com.br\' AND r.TotalParticipantes > 5"},'
            '"select_list":"descricao, data_agendamento, qtd_participantes, cliente_nome","group_by":"","order_by":"data_agendamento DESC","top":500,'
            '"explicacao_curta":"Lista reuniões do Wladmir com mais de 5 participantes"}',
        explicacao="Sem agregação; só lista. Tarefa excluída com 1=0.",
    ),
)


# ============================================================
# Dominio cravado
# ============================================================

CRM_OPERACAO_VENDEDOR = registrar(Dominio(
    nome="CRM_OPERACAO_VENDEDOR",
    descricao=(
        "Atividade operacional dos vendedores no CRM: tarefas pendentes/concluídas, "
        "atividades diárias, reuniões agendadas/realizadas, participantes. "
        "Use quando a pergunta envolver tarefa, follow-up, ligação, e-mail, atividade, "
        "reunião, meeting, agenda, participante, atrasado."
    ),
    palavras_chave=(
        "tarefa, atividade, followup, ligacao, email, reuniao, meeting, "
        "agenda, participante, atrasado, pendente, vendedor, operacao"
    ),
    base_conexao="crm",
    permissoes_necessarias=(),
    cte_template=CTE,
    cte_alias="operacao",
    tabelas_whitelist=(
        "Tarefas", "TipoTarefas", "Clients", "ClientContacts",
        "Reunioes", "TipoReuniao", "AspNetUsers",
    ),
    ramos=(
        Ramo(
            nome="tarefa", placeholder="FILTROS_TAREFA",
            descricao="Registros da tabela Tarefas (follow-ups, ligações, e-mails do vendedor).",
            colunas_filtraveis=FILTROS_TAREFA,
        ),
        Ramo(
            nome="reuniao", placeholder="FILTROS_REUNIAO",
            descricao="Registros da tabela Reunioes (meetings comerciais com transcrição/IA).",
            colunas_filtraveis=FILTROS_REUNIAO,
        ),
    ),
    colunas_resultado=(
        COL_TIPO, COL_ID, COL_DESCRICAO, COL_SUBTIPO, COL_STATUS,
        COL_DATA_AGENDAMENTO, COL_DATA_CONCLUSAO, COL_ATRASADA,
        COL_CLIENTE_NOME, COL_CONTATO_NOME,
        COL_VENDEDOR_EMAIL, COL_VENDEDOR_NOME, COL_QTD_PARTICIPANTES,
    ),
    few_shots=FEW_SHOTS,
    rules="""
- "Tarefa" = registro em Tarefas; "Reunião" = registro em Reunioes. CTE faz UNION ALL entre os dois.
- Para incluir só tarefas: tarefa = filtros; reuniao = "1=0".
- Para incluir só reuniões: tarefa = "1=0"; reuniao = filtros.
- "Atrasada":
  - Tarefa: t.TarefaExecutada = 0 AND t.DtReturn < GETDATE() AND c.FaseAtivo = 1 AND NOT EXISTS (SELECT 1 FROM Tarefas tnx WHERE tnx.ClientID = t.ClientID AND tnx.TarefaExecutada = 0 AND tnx.DtReturn > t.DtReturn). QUATRO condições, todas obrigatórias:
    1) não executada (TarefaExecutada=0);
    2) a DATA DE RETORNO já passou (DtReturn < GETDATE(); DtReturn = follow-up/deadline, NÃO a Data agendada);
    3) o lead está ATIVO (Clients.FaseAtivo=1) — sem isso o número infla com leads mortos;
    4) é a tarefa ATUAL do lead — NÃO existe outra tarefa aberta (TarefaExecutada=0) do MESMO cliente com DtReturn MAIOR. Cada lead acumula várias tarefas abertas empilhadas; reagendar cria uma tarefa NOVA com data futura e a velha vencida fica no banco. O dashboard só conta o lead pela última tarefa aberta — se já há um follow-up futuro, o lead NÃO está atrasado. SEM o NOT EXISTS o número infla ~12x contando linhas vencidas já substituídas (ex.: Eduarda dá 12 em vez de 1).
    Sempre inclua o NOT EXISTS ao contar/filtrar tarefas atrasadas. NÃO use DataExecucao IS NULL (vem preenchida mesmo em pendentes). Conclusão = TarefaExecutada.
  - Reunião: r.Status = 'Agendada' AND r.DataInicioAgendada < GETDATE(). NÃO use DataFimAgendada IS NULL — DataFimAgendada nunca é nula, então essa flag seria sempre 0.
- "Realizada"/"concluída":
  - Tarefa: t.TarefaExecutada = 1 (data em t.DataExecucao). "Pendente" = TarefaExecutada = 0.
  - Reunião: r.Status = 'Realizada' (NÃO existe 'Concluída'). Cancelada = r.Status = 'Cancelada'; agendada = r.Status = 'Agendada'.
- Tipo da tarefa (subtipo): use LIKE, não igualdade. Valores reais: 'Fazer ligação (Telefone)', 'WhatsApp', 'Enviar Email', 'Evento', 'Primeira reunião', 'Reunião técnica', 'Reunião de proposta', 'Envio de proposta', 'Feedback'. NÃO existe 'Follow-up'/'Ligação'/'E-mail' exatos.
- Subtipo da reunião (TipoReuniao.Descricao) é SEMPRE NULL (TipoReuniaoId não populado): NÃO agrupe/filtre reunião por subtipo. Para categorizar reuniões use 'status'.
- Vendedor da tarefa: AspNetUsers via Tarefas.UsuarioID.
- Vendedor da reunião: AspNetUsers via Reunioes.OrganizadorEmail = AspNetUsers.Email (não há FK direto). Fallback: COALESCE com Reunioes.OrganizadorNome/OrganizadorEmail quando o organizador não existe em AspNetUsers (~1 reunião sem match).
- TipoTarefas.Descricao e TipoReuniao.Descricao (não "Nome") são os rótulos legíveis.
- NÃO consultar LogTarefa (70 MB de auditoria) — fora da whitelist por design.
- "Minhas tarefas" = filtrar u.Email = e-mail do usuário autenticado.
""".strip(),
))
