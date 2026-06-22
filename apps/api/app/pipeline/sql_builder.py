"""Montagem do SQL final T-SQL a partir das partes do LLM (movido de services/pipeline.py)."""
from app.domains._base import Dominio
from app.core.sql_guard import validar_sql_readonly


def montar_sql_final(d: Dominio, partes: dict) -> str:
    cte = d.cte_template
    wheres = partes.get("wheres") or {}
    for ramo in d.ramos:
        where = wheres.get(ramo.nome) or "1=1"
        cte = cte.replace("{" + ramo.placeholder + "}", where)

    select_list = (partes.get("select_list") or "*").strip()
    group_by = (partes.get("group_by") or "").strip()
    order_by = (partes.get("order_by") or "").strip()
    top = int(partes.get("top") or 500)

    alias = d.cte_alias or "apolo_cte"
    sql_final = f"WITH {alias} AS (\n{cte}\n)\nSELECT TOP {top} {select_list} FROM {alias}"
    if group_by:
        sql_final += f"\nGROUP BY {group_by}"
    if order_by:
        sql_final += f"\nORDER BY {order_by}"

    validar_sql_readonly(sql_final)
    return sql_final
