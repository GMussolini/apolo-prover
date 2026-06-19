from pathlib import Path
from functools import lru_cache

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

@lru_cache(maxsize=10)
def carregar(nome: str) -> str:
    path = PROMPTS_DIR / f"{nome}.txt"
    if not path.exists():
        raise FileNotFoundError(f"prompt {nome} ausente em {path}")
    return path.read_text(encoding="utf-8")

def render(nome: str, **kwargs) -> str:
    # Substituição direcionada (não usar str.format: os prompts contêm
    # JSON literal com chaves { } que o format interpretaria como campos).
    template = carregar(nome)
    for chave, valor in kwargs.items():
        template = template.replace("{" + chave + "}", str(valor))
    return template
