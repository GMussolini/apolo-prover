"""Gerador do catálogo de schema.

Lê os dumps factuais (_dump/*.tsv) + o REGISTRY de domínios e emite UM YAML por
tabela usada (crm/<Tabela>.yaml, cr/<Tabela>.yaml) com os fatos do banco +
campos de enriquecimento (descricao, gotchas, queries_exemplo) para preencher.

Uso (dentro de apps/api):
    python -m app.schema_catalog._gerar            # gera só tabelas novas (preserva enriquecimento)
    python -m app.schema_catalog._gerar --force    # regenera tudo (apaga enriquecimento manual!)

Stdlib puro — sem pyyaml. A emissão é simples e controlada.
"""
from __future__ import annotations

import sys
from pathlib import Path

from app.domains import listar_ativos
from app.schema_catalog.loader import carregar_schema, TabelaReal

BASE_DIR = Path(__file__).parent


def _q(s: str) -> str:
    """Escala YAML segura (sempre entre aspas duplas)."""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _tabelas_por_dominio() -> dict[str, set[str]]:
    """{tabela: {dominios que a usam}}"""
    uso: dict[str, set[str]] = {}
    for dom in listar_ativos():
        for t in dom.tabelas_whitelist:
            uso.setdefault(t, set()).add(dom.nome)
    return uso


def _render(tab: TabelaReal, dominios: set[str]) -> str:
    pks = [c.nome for c in tab.colunas.values() if c.pk]
    rels = [
        f"{tab.nome}.{c.nome} -> {c.fk_para}"
        for c in tab.colunas.values() if c.fk_para
    ]

    out: list[str] = []
    out.append("# Catálogo de schema APOLO — fatos gerados de _dump/*.tsv por _gerar.py.")
    out.append("# Edite livremente descricao / gotchas / queries_exemplo (enriquecimento manual).")
    out.append(f"tabela: {tab.nome}")
    out.append(f"base: {tab.base}")
    out.append(f"linhas_aprox: {tab.linhas}")
    out.append(f"tamanho_mb: {tab.tamanho_mb}")
    out.append(f"chave_primaria: [{', '.join(pks) if pks else ''}]")
    out.append(f"usado_por_dominios: [{', '.join(sorted(dominios))}]")
    out.append("descricao: \"\"            # <- enriquecer: o que esta tabela representa no negócio")
    out.append("")
    out.append("colunas:")
    for c in tab.colunas.values():
        linha = (
            f"  - nome: {c.nome}\n"
            f"    tipo: {c.tipo}\n"
            f"    nulo: {str(c.nulo).lower()}"
        )
        if c.pk:
            linha += "\n    pk: true"
        if c.identity:
            linha += "\n    identity: true"
        if c.fk_para:
            linha += f"\n    fk_para: {c.fk_para}"
        linha += "\n    descricao: \"\""
        out.append(linha)
    out.append("")
    out.append("relacionamentos:")
    if rels:
        for r in rels:
            out.append(f"  - {_q(r)}")
    else:
        out.append("  []")
    out.append("")
    out.append("gotchas: []                # <- enriquecer: pegadinhas (col que não existe, nome enganoso, etc.)")
    out.append("")
    out.append("queries_exemplo: []        # <- enriquecer: [{pergunta: ..., sql: ...}]")
    out.append("")
    return "\n".join(out)


def main() -> int:
    force = "--force" in sys.argv
    schema = carregar_schema()
    uso = _tabelas_por_dominio()

    gerados, preservados, faltando = 0, 0, []
    for tabela, dominios in sorted(uso.items()):
        tab = schema.get(tabela)
        if tab is None:
            faltando.append(tabela)
            continue
        destino = BASE_DIR / tab.base / f"{tabela}.yaml"
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists() and not force:
            preservados += 1
            continue
        destino.write_text(_render(tab, dominios), encoding="utf-8")
        gerados += 1

    print(f"[catalogo] {gerados} gerados, {preservados} preservados (use --force pra regenerar)")
    if faltando:
        print(f"[catalogo] AVISO: tabelas no whitelist sem dump: {faltando}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
