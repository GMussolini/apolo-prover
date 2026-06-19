from dataclasses import dataclass, field
from typing import Literal

Base = Literal["crm", "cr"]
TipoColuna = Literal["str", "int", "float", "decimal", "date", "datetime", "bool", "enum"]


@dataclass(frozen=True)
class Coluna:
    """Ontologia rica de coluna disponível no resultado da CTE."""
    alias: str                              # alias humano usado no SQL final (ex: 'vendedor_email')
    expr: str                               # expressão SQL completa (ex: 'u.Email', 'COUNT(*)')
    tipo: TipoColuna
    descricao: str                          # semântica em PT-BR pro LLM entender
    nullable: bool = True
    agregavel: bool = False                 # SUM/AVG/MAX/MIN faz sentido?
    dimensao: bool = False                  # natural pra GROUP BY?
    enum_valores: tuple[str, ...] = ()      # valores válidos se enum
    filtravel: bool = True                  # pode aparecer em WHERE?


@dataclass(frozen=True)
class Ramo:
    """Sub-query dentro do CTE template (ex: 'pagar' e 'receber' no CR_FLUXO_CAIXA)."""
    nome: str
    placeholder: str                        # ex: 'FILTROS_PAGAR'
    descricao: str = ""
    colunas_filtraveis: tuple[Coluna, ...] = ()


@dataclass(frozen=True)
class FewShot:
    """Exemplo pergunta→SQL pra calibrar o LLM no domínio."""
    pergunta: str
    sql: str
    explicacao: str = ""


@dataclass(frozen=True)
class Dominio:
    """
    Domínio na abordagem híbrida (C):
    - cte_template define JOINs canônicos e tabelas autorizadas
    - LLM gera apenas wheres + select_list + group_by + order_by
    - Tabelas/JOINs nunca são compostos pelo LLM
    """
    nome: str
    descricao: str                          # vai pro classificador
    palavras_chave: str
    base_conexao: Base
    cte_template: str                       # JOINs canônicos + placeholders dos ramos ({FILTROS_X})
    cte_alias: str = "apolo_cte"            # nome do alias do CTE no SELECT final
    rules: str = ""                         # regras de negócio em texto livre
    ramos: tuple[Ramo, ...] = field(default_factory=tuple)
    colunas_resultado: tuple[Coluna, ...] = field(default_factory=tuple)
    """Colunas que aparecem no SELECT do CTE (saída). LLM escolhe daqui pra montar SELECT/GROUP BY/ORDER BY."""
    tabelas_whitelist: tuple[str, ...] = ()
    """Tabelas autorizadas dentro do cte_template — usado pelo sql_guard como defesa adicional."""
    few_shots: tuple[FewShot, ...] = field(default_factory=tuple)
    permissoes_necessarias: tuple[str, ...] = ()
