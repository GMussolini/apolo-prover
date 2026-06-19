from app.domains._base import Dominio, Ramo

REGISTRY: dict[str, Dominio] = {}


def registrar(d: Dominio) -> Dominio:
    if d.nome in REGISTRY:
        raise ValueError(f"dominio duplicado: {d.nome}")
    REGISTRY[d.nome] = d
    return d


def listar_ativos() -> list[Dominio]:
    return list(REGISTRY.values())


from app.domains import cr_folha_pessoas  # noqa: F401
from app.domains import crm_operacao  # noqa: F401
from app.domains import crm_pipeline  # noqa: F401
from app.domains import crm_coordenador  # noqa: F401
from app.domains import cr_fluxo_caixa  # noqa: F401
from app.domains import cr_delivery  # noqa: F401
from app.domains import crm_contatos  # noqa: F401
