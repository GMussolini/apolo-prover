"""Catálogo de schema do APOLO.

Fonte de detalhe (tabelas, colunas, tipos, FKs, relacionamentos, gotchas e
queries de exemplo) das bases CRM e CR, fora dos arquivos de domínio (serviço).

- `_dump/*.tsv`  : dump factual do banco (discovery). Fonte de verdade dos fatos.
- `crm/`, `cr/`  : um YAML por tabela (catálogo legível e enriquecível).
- `_gerar.py`    : regenera o esqueleto factual dos YAMLs a partir dos dumps.
- `loader.py`    : lê os dumps para validação (set tabela->colunas reais).

O teste `tests/test_catalog_consistency.py` usa o loader para garantir que NENHUM
domínio referencie coluna/tabela que não exista no banco — trava o build se citar.
"""
