"""CRM_COORDENADOR_IA — sistema interno do Coordenador Comercial IA.

Abordagem híbrida (C): CTE fixa com JOINs canônicos; LLM compõe SELECT/WHERE/GROUP BY/ORDER BY
escolhendo colunas declaradas na ontologia.

Cobre Casos, Passos, decisões da IA (RazaoDecisaoIa + ConfidenceIa + AgenteOrigem),
feedback do vendedor (👍/👎) e vendedor responsável.

Referência: Docs/APOLO_DISCOVERY/04-APOLO-dominios.md (item 5) +
            Docs/APOLO_DISCOVERY/01-CRM-discovery.md (cluster 4 — Coordenador IA).
"""
from app.domains import registrar
from app.domains._base import Dominio, Ramo, Coluna, FewShot


# ============================================================
# Colunas do resultado (saída do CTE) — LLM escolhe daqui no SELECT
# ============================================================

COL_PASSO_ID = Coluna(
    alias="passo_id", expr="passo_id", tipo="int",
    descricao="Id do passo de cadência (PassosCadenciaIa.Id).",
    nullable=False,
)
COL_CASO_ID = Coluna(
    alias="caso_id", expr="caso_id", tipo="int",
    descricao="Id do caso de cadência ao qual o passo pertence (CasosCadenciaIa.Id).",
    nullable=False,
)
COL_NUMERO_PASSO = Coluna(
    alias="numero_passo", expr="numero_passo", tipo="int",
    descricao="Sequência do passo dentro do caso (1, 2, 3...).",
    agregavel=True,
)
COL_CANAL = Coluna(
    alias="canal", expr="canal", tipo="int",
    descricao="Canal escolhido pela IA para o passo, em INT (enum). Conceitualmente telefone/email/linkedin/whatsapp, mas NÃO mapeados — filtre por código int (ex. observado: 2), nunca por string.",
    dimensao=True,
)
COL_PASSO_STATUS = Coluna(
    alias="passo_status", expr="passo_status", tipo="int",
    descricao="Resultado/desfecho do passo em INT (enum): 0 = pendente/sem resultado; demais (ex. 5, 7) = desfechos. Valores de enum não mapeados — não filtre por string.",
    dimensao=True,
)
COL_CASO_STATUS = Coluna(
    alias="caso_status", expr="caso_status", tipo="int",
    descricao="Status do caso em INT (enum). Conceitualmente Ativo/Pausado/Hibernado/Encerrado, mas os códigos não estão mapeados. NÃO filtre por string; para hibernação use HibernandoAte (data_hibernacao).",
    dimensao=True,
)
COL_DATA_AGENDADA = Coluna(
    alias="data_agendada", expr="data_agendada", tipo="datetime",
    descricao="Data em que o passo foi agendado pela IA.",
    dimensao=True,
)
COL_DATA_EXECUCAO = Coluna(
    alias="data_execucao", expr="data_execucao", tipo="datetime",
    descricao="Data em que o passo foi efetivamente executado (NULL se ainda pendente).",
    dimensao=True,
)
COL_RAZAO_DECISAO_IA = Coluna(
    alias="razao_decisao_ia", expr="razao_decisao_ia", tipo="str",
    descricao="Texto explicando o porquê da IA ter tomado a decisão deste passo (auditável).",
)
COL_CONFIDENCE_IA = Coluna(
    alias="confidence_ia", expr="confidence_ia", tipo="int",
    descricao="Confiança da IA na decisão, INT em escala 0-100 (NÃO decimal 0-1). Baixa < 60, alta >= 80. Para média use AVG(CAST(confidence_ia AS float)).",
    agregavel=True,
)
COL_AGENTE_ORIGEM = Coluna(
    alias="agente_origem", expr="agente_origem", tipo="str",
    descricao="Nome do agente IA que originou o passo. Valores reais observados: 'CadenciaAgente', 'BackfillCarteiraService'. A lista pode crescer — use SELECT DISTINCT agente_origem para descobrir.",
    dimensao=True,
)
COL_VENDEDOR_EMAIL = Coluna(
    alias="vendedor_email", expr="vendedor_email", tipo="str",
    descricao="E-mail do vendedor dono do caso (AspNetUsers.Email).",
    dimensao=True,
)
COL_FEEDBACK_UTIL = Coluna(
    alias="feedback_util", expr="feedback_util", tipo="bool",
    descricao="Feedback do vendedor sobre o passo: 1 = 👍 útil, 0 = 👎 não útil, NULL = sem feedback.",
    dimensao=True,
)
COL_FEEDBACK_OBSERVACAO = Coluna(
    alias="feedback_observacao", expr="feedback_observacao", tipo="str",
    descricao="Observação textual deixada pelo vendedor junto do feedback. Pode estar sempre vazia se FeedbackPassoIa não tiver dados.",
)
COL_DATA_HIBERNACAO = Coluna(
    alias="data_hibernacao", expr="data_hibernacao", tipo="datetime",
    descricao="Data/hora até quando o caso permanece hibernado (CasosCadenciaIa.HibernandoAte). Caso hibernando = data_hibernacao IS NOT NULL AND data_hibernacao > GETDATE().",
    dimensao=True,
)
COL_PROXIMA_ACAO = Coluna(
    alias="proxima_acao", expr="proxima_acao", tipo="datetime",
    descricao="Data/hora agendada para a próxima ação da IA no caso (CasosCadenciaIa.ProximaAcaoEm). Caso atrasado = proxima_acao < GETDATE().",
    dimensao=True,
)
COL_ULTIMA_ACAO = Coluna(
    alias="ultima_acao", expr="ultima_acao", tipo="datetime",
    descricao="Data/hora da última ação executada no caso (CasosCadenciaIa.UltimaAcaoEm).",
    dimensao=True,
)
COL_SCORE = Coluna(
    alias="score", expr="score", tipo="int",
    descricao="Score atual do caso/lead calculado pela IA (CasosCadenciaIa.ScoreAtual). Quanto maior, mais quente.",
    agregavel=True,
)
COL_NUMERO_TENTATIVAS = Coluna(
    alias="numero_tentativas", expr="numero_tentativas", tipo="int",
    descricao="Número total de tentativas de contato realizadas no caso (CasosCadenciaIa.NumeroTentativas).",
    agregavel=True,
)
COL_TENTATIVAS_SEM_SUCESSO = Coluna(
    alias="tentativas_sem_sucesso", expr="tentativas_sem_sucesso", tipo="int",
    descricao="Tentativas consecutivas sem sucesso no caso (CasosCadenciaIa.TentativasSemSucesso); insumo para hibernar/encerrar.",
    agregavel=True,
)


# ============================================================
# Colunas filtráveis do ramo — LLM usa aqui pra montar WHERE
# ============================================================

FILTROS_PRINCIPAL = (
    Coluna(alias="vendedor_email", expr="u.Email", tipo="str",
           descricao="E-mail do vendedor dono do caso."),
    Coluna(alias="canal", expr="p.Canal", tipo="int",
           descricao="Canal do passo em INT (enum); telefone/email/linkedin/whatsapp NÃO mapeados — filtre por código int (ex. observado: 2), nunca por string."),
    Coluna(alias="passo_status", expr="p.Resultado", tipo="int",
           descricao="Resultado/estado do passo (int). 0 = pendente/sem resultado; demais valores = desfechos da execução. Não filtre por string."),
    Coluna(alias="caso_status", expr="c.Status", tipo="int",
           descricao="Status do caso (int enum); Ativo/Pausado/Hibernado/Encerrado NÃO mapeados. Para hibernação use o filtro data_hibernacao (c.HibernandoAte), não Status por string."),
    Coluna(alias="agente_origem", expr="p.AgenteOrigem", tipo="str",
           descricao="Agente IA que originou o passo."),
    Coluna(alias="confidence_ia", expr="p.ConfidenceIa", tipo="int",
           descricao="Confiança da IA. Use >=, <=, BETWEEN."),
    Coluna(alias="data_agendada", expr="p.DataPrevista", tipo="datetime",
           descricao="Data prevista/agendada pela IA. Use >=, <=, BETWEEN."),
    Coluna(alias="data_execucao", expr="p.ExecutadaEm", tipo="datetime",
           descricao="Data de execução real. IS NULL = pendente."),
    Coluna(alias="numero_passo", expr="p.Ordem", tipo="int",
           descricao="Sequência (ordem) do passo no caso."),
    Coluna(alias="feedback_util", expr="f.Avaliacao", tipo="bool",
           descricao="Feedback do vendedor: 1 = útil, 0 = não útil, IS NULL = sem feedback."),
    Coluna(alias="data_hibernacao", expr="c.HibernandoAte", tipo="datetime",
           descricao="Até quando o caso hiberna. Caso hibernando: c.HibernandoAte IS NOT NULL AND c.HibernandoAte > GETDATE()."),
    Coluna(alias="proxima_acao", expr="c.ProximaAcaoEm", tipo="datetime",
           descricao="Próxima ação agendada do caso. Caso atrasado: c.ProximaAcaoEm < GETDATE()."),
    Coluna(alias="ultima_acao", expr="c.UltimaAcaoEm", tipo="datetime",
           descricao="Data da última ação executada no caso. Use >=, <=, BETWEEN."),
    Coluna(alias="score", expr="c.ScoreAtual", tipo="int",
           descricao="Score atual do caso/lead (int). Use >=, <=, BETWEEN."),
    Coluna(alias="numero_tentativas", expr="c.NumeroTentativas", tipo="int",
           descricao="Total de tentativas de contato no caso (int)."),
    Coluna(alias="tentativas_sem_sucesso", expr="c.TentativasSemSucesso", tipo="int",
           descricao="Tentativas consecutivas sem sucesso no caso (int)."),
)


# ============================================================
# CTE template — JOINs canônicos, LLM nunca altera
# ============================================================

CTE = """
SELECT p.Id              AS passo_id,
       c.Id              AS caso_id,
       p.Ordem           AS numero_passo,
       p.Canal           AS canal,
       p.Resultado       AS passo_status,
       c.Status          AS caso_status,
       p.DataPrevista    AS data_agendada,
       p.ExecutadaEm     AS data_execucao,
       p.RazaoDecisaoIa  AS razao_decisao_ia,
       p.ConfidenceIa    AS confidence_ia,
       p.AgenteOrigem    AS agente_origem,
       u.Email           AS vendedor_email,
       f.Avaliacao       AS feedback_util,
       f.ObservacaoCurta AS feedback_observacao,
       c.HibernandoAte   AS data_hibernacao,
       c.ProximaAcaoEm   AS proxima_acao,
       c.UltimaAcaoEm    AS ultima_acao,
       c.ScoreAtual      AS score,
       c.NumeroTentativas AS numero_tentativas,
       c.TentativasSemSucesso AS tentativas_sem_sucesso
FROM PassosCadenciaIa p
INNER JOIN CasosCadenciaIa c ON c.Id = p.CasoCadenciaIaId
LEFT JOIN FeedbackPassoIa f  ON f.PassoId = p.Id
LEFT JOIN AspNetUsers u      ON u.Id = c.UsuarioVendedorId
WHERE ({FILTROS_PRINCIPAL})
""".strip()


# ============================================================
# Few-shot examples — calibram o LLM no estilo de resposta
# ============================================================

FEW_SHOTS = (
    FewShot(
        pergunta="Quantos passos a IA gerou para o Felipe nos ultimos 7 dias e qual a confidence media?",
        sql='{"wheres":{"principal":"u.Email = \'foliveira@provertec.com.br\' AND p.DataPrevista >= DATEADD(day,-7,GETDATE())"},'
            '"select_list":"COUNT(*) AS total_passos, AVG(CAST(confidence_ia AS float)) AS confidence_media","group_by":"","order_by":"","top":1,'
            '"explicacao_curta":"Total de passos e confidence média (escala 0-100) do Felipe nos últimos 7 dias"}',
        explicacao="Filtro por vendedor + janela temporal. COUNT + AVG na mesma linha (top=1). ConfidenceIa é INT 0-100: use CAST AS float pra média não truncar; a escala da resposta é 0-100.",
    ),
    FewShot(
        pergunta="Casos hibernando por vendedor",
        sql='{"wheres":{"principal":"c.HibernandoAte IS NOT NULL AND c.HibernandoAte > GETDATE()"},'
            '"select_list":"vendedor_email, COUNT(DISTINCT caso_id) AS casos_hibernados","group_by":"vendedor_email","order_by":"casos_hibernados DESC","top":50,'
            '"explicacao_curta":"Ranking de vendedores com mais casos hibernados"}',
        explicacao="Hibernação confiável vem de HibernandoAte (Status é INT enum não mapeado, não filtre por string). COUNT DISTINCT no caso_id (granularidade é passo, e um caso tem vários passos). GROUP BY vendedor.",
    ),
    FewShot(
        pergunta="Taxa de aceitacao 👍/👎 por agente origem",
        sql='{"wheres":{"principal":"f.Avaliacao IS NOT NULL"},'
            '"select_list":"agente_origem, SUM(CASE WHEN feedback_util = 1 THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*),0) AS taxa_util_pct, COUNT(*) AS total_feedbacks",'
            '"group_by":"agente_origem","order_by":"taxa_util_pct DESC","top":20,'
            '"explicacao_curta":"% de feedback útil por agente, considerando apenas passos com feedback"}',
        explicacao="CASE+SUM pra taxa, NULLIF pra evitar div/0, filtra só quem tem feedback (Util IS NOT NULL).",
    ),
    FewShot(
        pergunta="Passos pendentes com confidence baixa (<60)",
        sql='{"wheres":{"principal":"p.ExecutadaEm IS NULL AND p.ConfidenceIa < 60"},'
            '"select_list":"passo_id, caso_id, vendedor_email, canal, confidence_ia, razao_decisao_ia, data_agendada","group_by":"","order_by":"confidence_ia ASC","top":100,'
            '"explicacao_curta":"Lista passos pendentes com baixa confiança da IA (< 60 em escala 0-100) para revisão"}',
        explicacao="Sem agregação; lista detalhe. ConfidenceIa é INT 0-100: baixa < 60. Ordena pela confidence crescente (pior primeiro).",
    ),
)


# ============================================================
# Dominio cravado
# ============================================================

CRM_COORDENADOR_IA = registrar(Dominio(
    nome="CRM_COORDENADOR_IA",
    descricao=(
        "Sistema interno do Coordenador Comercial IA: casos de cadência, passos com "
        "decisão da IA (razão + confidence + agente origem), feedback 👍/👎 do vendedor "
        "e vendedor responsável. "
        "Use quando a pergunta envolver Coordenador IA, cadência, caso, passo, "
        "agente IA, confidence, razão de decisão, feedback, kanban V2, aprendizado, "
        "regra aprendida, hibernação, prospecção dirigida por IA."
    ),
    palavras_chave=(
        "coordenador, IA, cadencia, caso, passo, feedback, confidence, agente, "
        "regra, aprendizado, decisao, kanban, hibernado, prospeccao"
    ),
    base_conexao="crm",
    permissoes_necessarias=("coordenador",),
    cte_template=CTE,
    cte_alias="coordenador",
    tabelas_whitelist=(
        "PassosCadenciaIa", "CasosCadenciaIa", "FeedbackPassoIa", "AspNetUsers",
    ),
    ramos=(
        Ramo(
            nome="principal", placeholder="FILTROS_PRINCIPAL",
            descricao="Passos de cadência com seus casos, feedback e vendedor.",
            colunas_filtraveis=FILTROS_PRINCIPAL,
        ),
    ),
    colunas_resultado=(
        COL_PASSO_ID, COL_CASO_ID, COL_NUMERO_PASSO, COL_CANAL,
        COL_PASSO_STATUS, COL_CASO_STATUS, COL_DATA_AGENDADA, COL_DATA_EXECUCAO,
        COL_RAZAO_DECISAO_IA, COL_CONFIDENCE_IA, COL_AGENTE_ORIGEM,
        COL_VENDEDOR_EMAIL, COL_FEEDBACK_UTIL, COL_FEEDBACK_OBSERVACAO,
        COL_DATA_HIBERNACAO, COL_PROXIMA_ACAO, COL_ULTIMA_ACAO,
        COL_SCORE, COL_NUMERO_TENTATIVAS, COL_TENTATIVAS_SEM_SUCESSO,
    ),
    few_shots=FEW_SHOTS,
    rules="""
- Granularidade do CTE = passo (PassosCadenciaIa). Um caso pode ter vários passos.
- Para contar casos distintos, use COUNT(DISTINCT caso_id).
- Para contar passos, COUNT(*) basta.
- ConfidenceIa é INT em escala 0-100, NÃO decimal 0-1. "Baixa confidence" = < 60; "alta" >= 80. Nunca filtre < 0.6 / < 1 (retorna 0 linhas). Para média use AVG(CAST(confidence_ia AS float)); a escala da resposta é 0-100.
- passo_status (p.Resultado) é INT (enum): 0 = pendente/sem resultado; demais (ex. 5, 7) = desfechos. NÃO filtre por string ('Concluido'/'Falhou' não existem).
- canal (p.Canal) é INT (enum): telefone/email/linkedin/whatsapp NÃO mapeados — filtre por código int (ex. observado: 2), nunca por string.
- caso_status (c.Status) é INT (enum): Ativo/Pausado/Hibernado/Encerrado NÃO mapeados — não filtre por string.
- Passos pendentes: p.ExecutadaEm IS NULL.
- Passos executados: p.ExecutadaEm IS NOT NULL.
- Caso em hibernação: c.HibernandoAte IS NOT NULL AND c.HibernandoAte > GETDATE() (hibernação confiável vem de HibernandoAte/TentativasSemSucesso, NÃO de c.Status por string).
- Caso com próxima ação atrasada: c.ProximaAcaoEm < GETDATE().
- Feedback do vendedor: f.Avaliacao = 1 (👍) ou 0 (👎). NULL = vendedor não avaliou ainda.
- FeedbackPassoIa pode estar vazia (sistema implantado, feedback ainda não usado); se a pergunta de feedback retornar vazio, é ausência de dados, não erro.
- Vendedor sempre identificado por AspNetUsers.Email; o vínculo é CasosCadenciaIa.UsuarioVendedorId -> AspNetUsers.Id.
- AgenteOrigem identifica qual agente IA gerou o passo. Valores reais observados: 'CadenciaAgente', 'BackfillCarteiraService' (a lista pode crescer; use SELECT DISTINCT agente_origem para descobrir).
- Domínio restrito a Coordenador + Admin (whitelist em prod com Diego). LLM não deve sugerir compartilhar pra vendedor comum.
""".strip(),
))
