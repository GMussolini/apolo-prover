import pandas as pd


class FakeLLM:
    """Devolve respostas gravadas em ordem FIFO. Conta chamadas."""
    def __init__(self, roteiro: list[dict]):
        self.roteiro = list(roteiro)
        self.chamadas: list[dict] = []

    def _next(self, kind: str, **kw) -> dict:
        self.chamadas.append({"kind": kind, **kw})
        if not self.roteiro:
            raise AssertionError(f"FakeLLM sem roteiro para chamada {kind}")
        entry = self.roteiro.pop(0)
        if entry.get("raise"):
            raise RuntimeError(entry["raise"])
        return entry

    async def chat_json(self, modelo, system, user, max_tokens=1500, temperatura=0.0) -> dict:
        return self._next("json", modelo=modelo)

    async def chat_texto(self, modelo, system, user, max_tokens=500, temperatura=0.3) -> dict:
        return self._next("texto", modelo=modelo)

    def estimar_custo(self, modelo, ti, to) -> float:
        return round((ti + to) / 1_000_000, 6)


class FakeSql:
    def __init__(self, resultado):
        self.resultado = resultado
        self.queries: list[str] = []

    async def execute_query(self, base, sql, params=None, timeout=30) -> pd.DataFrame:
        self.queries.append(sql)
        if isinstance(self.resultado, Exception):
            raise self.resultado
        return pd.DataFrame.from_records(self.resultado)


class FakeStore:
    def __init__(self, historico=None):
        self.historico = historico or []
        self.saved: list[dict] = []

    async def load_history(self, sessao_id, limite=5):
        return list(self.historico)

    async def save_turn(self, **kwargs):
        self.saved.append(kwargs)


async def coletar_eventos(agen) -> list[dict]:
    return [ev async for ev in agen]
