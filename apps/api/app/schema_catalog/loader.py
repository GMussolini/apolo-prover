"""Leitura dos dumps factuais do schema (stdlib puro — sem pyyaml).

Usado pelo gerador do catálogo e pelo teste-guardião de consistência.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DUMP_DIR = Path(__file__).parent / "_dump"


@dataclass(frozen=True)
class ColunaReal:
    nome: str
    tipo: str
    max_len: str
    nulo: bool
    identity: bool
    pk: bool
    fk_para: str | None  # ex: "dbo.AspNetUsers" ou None


@dataclass
class TabelaReal:
    base: str            # "crm" | "cr"
    nome: str
    linhas: int = 0
    tamanho_mb: float = 0.0
    colunas: dict[str, ColunaReal] = field(default_factory=dict)  # nome -> ColunaReal


def _ler_tsv(path: Path) -> list[list[str]]:
    # utf-8-sig remove o BOM do header exportado pelo SQL Server
    linhas = path.read_text(encoding="utf-8-sig").splitlines()
    return [l.split("\t") for l in linhas if l.strip()]


@lru_cache(maxsize=1)
def carregar_schema() -> dict[str, TabelaReal]:
    """Retorna {nome_tabela: TabelaReal} unindo CRM e CR a partir dos dumps."""
    tabelas: dict[str, TabelaReal] = {}

    for base, cols_file, tab_file in (
        ("crm", "CRM_colunas.tsv", "CRM_tabelas.tsv"),
        ("cr", "CR_colunas.tsv", "CR_tabelas.tsv"),
    ):
        # tamanho / linhas
        meta: dict[str, tuple[int, float]] = {}
        for row in _ler_tsv(DUMP_DIR / tab_file)[1:]:
            # Schema, Tabela, Rows, SizeMB
            if len(row) >= 4:
                meta[row[1]] = (int(row[2] or 0), float(row[3] or 0))

        # colunas: Schema, Tabela, Coluna, Tipo, MaxLen, Null, Ident, PK, FKTo
        for row in _ler_tsv(DUMP_DIR / cols_file)[1:]:
            if len(row) < 8:
                continue
            _, tab, col, tipo, maxlen, nulo, ident, pk = row[:8]
            fk = row[8] if len(row) >= 9 and row[8] else None
            t = tabelas.get(tab)
            if t is None:
                linhas, mb = meta.get(tab, (0, 0.0))
                t = TabelaReal(base=base, nome=tab, linhas=linhas, tamanho_mb=mb)
                tabelas[tab] = t
            t.colunas[col] = ColunaReal(
                nome=col, tipo=tipo, max_len=maxlen,
                nulo=(nulo == "1"), identity=(ident == "1"),
                pk=(pk == "1"), fk_para=fk,
            )

    return tabelas


def colunas_de(tabela: str) -> set[str]:
    """Conjunto de nomes de coluna reais de uma tabela (vazio se tabela inexistente)."""
    t = carregar_schema().get(tabela)
    return set(t.colunas) if t else set()
