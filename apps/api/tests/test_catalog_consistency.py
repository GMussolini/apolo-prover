"""Teste-guardião: garante que NENHUM domínio referencie tabela/coluna inexistente.

Varre, para cada domínio do REGISTRY:
- tabelas_whitelist ⊆ schema real
- todo `alias.Coluna` no cte_template
- todo `alias.Coluna` nos FILTROS_* (expr das colunas filtráveis)
- todo `alias.Coluna` nos few-shots (wheres)

Resolve `alias` -> tabela pelos FROM/JOIN do CTE e valida a coluna contra o dump
real (app/schema_catalog/_dump/*.tsv). Se citar coluna que não existe, o build
fica vermelho — exatamente a classe de bug do `Invalid column name 'AreaAtuacaoId'`.
"""
from __future__ import annotations

import json
import re

from app.domains import listar_ativos
from app.schema_catalog.loader import carregar_schema

# captura "FROM Tabela alias" e "JOIN Tabela alias" (ignora a keyword ON seguinte)
_ALIAS_RE = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_]\w*)\s+([A-Za-z_]\w*)", re.IGNORECASE)
# captura referências alias.coluna
_REF_RE = re.compile(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b")
# literais string SQL ('...') — removidos antes de extrair refs (evita pegar e-mails)
_LIT_RE = re.compile(r"'[^']*'")
# aliases que não são tabelas (keywords após FROM/JOIN não capturadas, mas por segurança)
_NAO_ALIAS = {"on", "as", "left", "right", "inner", "outer", "join", "where", "and", "or"}


def _alias_map(sql: str) -> dict[str, str]:
    m: dict[str, str] = {}
    for tabela, alias in _ALIAS_RE.findall(sql):
        if alias.lower() not in _NAO_ALIAS:
            m[alias] = tabela
    return m


def _refs(sql: str) -> list[tuple[str, str]]:
    return _REF_RE.findall(_LIT_RE.sub("", sql))


def test_dominios_referenciam_apenas_schema_real():
    schema = carregar_schema()
    tabelas_reais = set(schema)
    erros: list[str] = []

    for dom in listar_ativos():
        # 1) whitelist
        for t in dom.tabelas_whitelist:
            if t not in tabelas_reais:
                erros.append(f"[{dom.nome}] tabela '{t}' do whitelist não existe no schema real")

        amap = _alias_map(dom.cte_template)

        def checar(sql: str, origem: str, mapa: dict[str, str]):
            for alias, col in _refs(sql):
                tab = mapa.get(alias)
                if tab is None:
                    continue  # alias não-resolvível (output do CTE, subquery externa) — lenient
                if tab not in schema:
                    erros.append(f"[{dom.nome}] {origem}: tabela '{tab}' (alias {alias}) não existe")
                elif col not in schema[tab].colunas:
                    erros.append(f"[{dom.nome}] {origem}: coluna '{tab}.{col}' não existe")

        # 2) CTE template
        checar(dom.cte_template, "CTE", amap)

        # 3) FILTROS_* (expr das colunas filtráveis)
        for ramo in dom.ramos:
            for c in ramo.colunas_filtraveis:
                checar(c.expr, f"FILTRO {ramo.nome}.{c.alias}", amap)

        # 4) few-shots (wheres) — alias map aumentado com FROM/JOIN locais do exemplo
        for i, fs in enumerate(dom.few_shots):
            try:
                data = json.loads(fs.sql)
            except (json.JSONDecodeError, TypeError):
                erros.append(f"[{dom.nome}] few-shot #{i} não é JSON válido")
                continue
            wheres = data.get("wheres", {})
            fs_sql = " ".join(str(v) for v in wheres.values())
            mapa_fs = {**amap, **_alias_map(fs_sql)}
            checar(fs_sql, f"few-shot #{i}", mapa_fs)

    assert not erros, "Referências de schema inválidas nos domínios:\n- " + "\n- ".join(erros)
