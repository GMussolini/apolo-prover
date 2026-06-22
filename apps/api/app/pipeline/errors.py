from typing import Literal


class TurnFinished(Exception):
    """Short-circuit: a resposta normal já foi emitida pelo estágio."""


class ApoloError(Exception):
    def __init__(self, mensagem_amigavel: str, codigo_log: str,
                 modo: Literal["error_event", "token_stream"], causa: Exception | None = None):
        super().__init__(codigo_log)
        self.mensagem_amigavel = mensagem_amigavel
        self.codigo_log = codigo_log
        self.modo = modo
        self.causa = causa


class RateLimited(ApoloError):
    def __init__(self, detail: str):
        super().__init__(str(detail), "rate_limit", "error_event", causa=detail)

class ClassifyFailed(ApoloError):
    def __init__(self, causa=None):
        super().__init__("Não consegui entender sua pergunta. Tente reformular.", "classificador", "error_event", causa)

class SqlGenFailed(ApoloError):
    def __init__(self, causa=None):
        super().__init__("Tive um problema gerando a consulta. Tente reformular a pergunta.", "sql_generator", "token_stream", causa)

class SqlBlocked(ApoloError):
    def __init__(self, causa=None):
        super().__init__("A consulta gerada foi bloqueada por segurança. Tente reformular.", "sql_invalido", "token_stream", causa)

class SqlBuildFailed(ApoloError):
    def __init__(self, causa=None):
        super().__init__("Não consegui montar a consulta. Tente reformular.", "montar_sql", "token_stream", causa)

class SqlExecFailed(ApoloError):
    def __init__(self, causa=None):
        super().__init__("Não consegui consultar a base no momento. Tente de novo em instantes.", "execucao_sql", "token_stream", causa)

class AnswerFailed(ApoloError):
    def __init__(self, canal: str, causa=None):
        if canal == "voz":
            msg, cod = "Consegui os dados, mas falhei em narrar. Tente de novo.", "response_voice"
        else:
            msg, cod = "Consegui os dados, mas falhei em formatar a resposta. Tente de novo.", "response_generator"
        super().__init__(msg, cod, "token_stream", causa)
