PERMISSOES_DISPONIVEIS = ("coordenador", "financeiro", "rh", "delivery")


def usuario_pode(usuario_permissoes: str, dominio_requer: tuple[str, ...], is_admin: bool = False) -> bool:
    if is_admin:
        return True
    if not dominio_requer:
        return True
    user_perms = {p.strip() for p in usuario_permissoes.split(",") if p.strip()}
    return any(p in user_perms for p in dominio_requer)
