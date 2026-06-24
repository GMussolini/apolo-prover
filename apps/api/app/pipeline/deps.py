from dataclasses import dataclass
from app.core.config import Config, get_config
from app.ports.llm import LLMPort, AnthropicAdapter
from app.ports.sql_exec import SqlExecPort, SqlAdapter
from app.ports.turn_store import TurnStorePort, HistoricoTurnStore


@dataclass
class Deps:
    llm: LLMPort
    sql: SqlExecPort
    store: TurnStorePort
    cfg: Config


def default_deps() -> Deps:
    return Deps(llm=AnthropicAdapter(), sql=SqlAdapter(), store=HistoricoTurnStore(), cfg=get_config())
