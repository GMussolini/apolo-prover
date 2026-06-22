from app.pipeline.errors import (ApoloError, TurnFinished, RateLimited, ClassifyFailed,
                                  SqlGenFailed, SqlBlocked, SqlExecFailed, AnswerFailed)

def test_modos_e_mensagens():
    assert RateLimited("limite").modo == "error_event"
    assert ClassifyFailed(None).modo == "error_event"
    assert ClassifyFailed(None).mensagem_amigavel == "Não consegui entender sua pergunta. Tente reformular."
    assert SqlGenFailed().modo == "token_stream"
    assert SqlExecFailed().mensagem_amigavel.startswith("Não consegui consultar a base")
    assert AnswerFailed("voz").mensagem_amigavel == "Consegui os dados, mas falhei em narrar. Tente de novo."
    assert AnswerFailed("texto").mensagem_amigavel.startswith("Consegui os dados, mas falhei em formatar")
    assert issubclass(SqlBlocked, ApoloError)
    assert issubclass(TurnFinished, Exception)
