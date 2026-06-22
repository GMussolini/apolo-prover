"""Pipeline da abordagem híbrida (C):
- CTE template definido no domínio (JOINs canônicos)
- LLM responde com partes restritas: wheres por ramo, select_list, group_by, order_by, top
- Backend monta SQL final amarrando dentro do CTE
- Tabelas/JOINs nunca compostos pelo LLM
"""
import json
import re
import unicodedata
from app.domains._base import Dominio


def render_lista_dominios(dominios) -> str:
    """Lista compacta pro classificador."""
    return "\n".join(
        f"- **{d.nome}** (base={d.base_conexao}): {d.descricao}"
        for d in dominios
    )


def _normalizar(texto: str) -> str:
    """lowercase + remove acentos pra casar palavras-chave de forma robusta."""
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def render_sinais_lexicais(dominios, pergunta: str) -> str:
    """Híbrido léxico: conta matches das palavras_chave de cada domínio na pergunta.
    É SINAL DE APOIO pro classificador LLM — não decide sozinho (evita falso-positivo
    de cosseno). Ex.: 'faturando'+'dev' apontam CR_FOLHA_PESSOAS."""
    pq = _normalizar(pergunta)
    tokens = set(re.findall(r"[a-z0-9]+", pq))
    resultados = []
    for d in dominios:
        kws = [k.strip() for k in (d.palavras_chave or "").split(",") if k.strip()]
        hits = []
        for kw in kws:
            kwn = _normalizar(kw)
            if len(kwn) < 3:
                continue
            casou = (kwn in pq) if " " in kwn else (kwn in tokens or any(kwn in tok for tok in tokens))
            if casou:
                hits.append(kw)
        if hits:
            resultados.append((d.nome, hits))
    resultados.sort(key=lambda x: -len(x[1]))
    if not resultados:
        return "(nenhuma palavra-chave de dominio casou — decida pela semantica das descricoes)"
    return "\n".join(
        f"- {nome}: {len(hits)} match(es) [{', '.join(hits[:8])}]" for nome, hits in resultados
    )


def render_ontologia_colunas(d: Dominio) -> str:
    """Lista colunas do resultado da CTE com semântica pro LLM escolher SELECT/GROUP BY/ORDER BY."""
    if not d.colunas_resultado:
        return "(domínio sem colunas declaradas — use '*')"
    lines = []
    for c in d.colunas_resultado:
        tags = []
        if c.agregavel:
            tags.append("agregavel")
        if c.dimensao:
            tags.append("dimensao")
        if c.enum_valores:
            tags.append("enum=[" + ",".join(c.enum_valores) + "]")
        if not c.nullable:
            tags.append("not_null")
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        lines.append(f"- **{c.alias}** ({c.tipo}){tag_str}: {c.descricao}")
    return "\n".join(lines)


def render_ramos_filtraveis(d: Dominio) -> str:
    """Lista filtros disponíveis por ramo (mapa alias→expressão SQL)."""
    if not d.ramos:
        return "(domínio sem ramos)"
    blocks = []
    for r in d.ramos:
        cols = "\n".join(
            f"  - {c.alias} ({c.tipo}): {c.descricao}"
            for c in r.colunas_filtraveis
        )
        blocks.append(f"### Ramo: {r.nome} (placeholder: {{{r.placeholder}}})\n{r.descricao}\nFiltros disponíveis:\n{cols}")
    return "\n\n".join(blocks)


def render_few_shots(d: Dominio) -> str:
    """Examples few-shot pro LLM calibrar tom e estilo de resposta."""
    if not d.few_shots:
        return "(sem exemplos cravados)"
    parts = []
    for i, fs in enumerate(d.few_shots, 1):
        parts.append(
            f"Exemplo {i}:\n"
            f"Pergunta: {fs.pergunta}\n"
            f"SQL (partes):\n```json\n{fs.sql}\n```\n"
            + (f"Explicação: {fs.explicacao}\n" if fs.explicacao else "")
        )
    return "\n".join(parts)


def contexto_para_classificador(dominios, pergunta: str = "") -> dict:
    """Retorna estrutura serializável usada no prompt intent_classification."""
    return {
        "lista_dominios": render_lista_dominios(dominios),
        "sinais_lexicais": render_sinais_lexicais(dominios, pergunta),
    }


def contexto_para_sql_generator(d: Dominio, pergunta_reformulada: str) -> dict:
    """Retorna estrutura serializável usada no prompt sql_generator (abordagem híbrida)."""
    return {
        "dominio_nome": d.nome,
        "dominio_descricao": d.descricao,
        "base_conexao": d.base_conexao,
        "rules": d.rules or "(sem regras adicionais)",
        "cte_template_visivel": d.cte_template,
        "cte_alias": d.cte_alias,
        "ontologia_colunas": render_ontologia_colunas(d),
        "ramos_filtraveis": render_ramos_filtraveis(d),
        "few_shots": render_few_shots(d),
        "pergunta": pergunta_reformulada,
        "placeholders_ramos": ", ".join(f"{{{r.placeholder}}}" for r in d.ramos),
    }
