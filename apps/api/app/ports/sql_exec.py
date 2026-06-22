from typing import Protocol
import pandas as pd
from app.core import database


class SqlExecPort(Protocol):
    async def execute_query(self, base: str, sql: str, params: dict | None = None,
                           timeout: int = 30) -> pd.DataFrame: ...


class SqlAdapter:
    async def execute_query(self, base, sql, params=None, timeout=30) -> pd.DataFrame:
        return await database.execute_query(base, sql, params, timeout)
