from app.core.logging_config import filtrar_segredos


def test_filtra_password():
    event = {"msg": "connecting password=secret123"}
    resultado = filtrar_segredos(None, None, dict(event))
    assert "secret123" not in resultado["msg"]
    assert "***" in resultado["msg"]


def test_filtra_anthropic_key():
    event = {"msg": "using sk-ant-api03-abcdef-key"}
    resultado = filtrar_segredos(None, None, dict(event))
    assert "sk-ant-api03" not in resultado["msg"]
    assert "***" in resultado["msg"]
