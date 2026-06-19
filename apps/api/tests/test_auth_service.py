import pytest
from datetime import timedelta
from app.services.auth_service import hash_senha, verificar_senha, criar_access_token, decodificar_token


def test_hash_e_verifica_senha():
    h = hash_senha("MinhaSenh@123")
    assert verificar_senha("MinhaSenh@123", h)
    assert not verificar_senha("errada", h)


def test_token_round_trip():
    token = criar_access_token({"sub": "42", "permissoes": "coordenador,rh"}, expira_em=timedelta(minutes=5))
    payload = decodificar_token(token)
    assert payload["sub"] == "42"
    assert payload["permissoes"] == "coordenador,rh"


def test_token_expirado(monkeypatch):
    from app.services import auth_service
    token = criar_access_token({"sub": "1"}, expira_em=timedelta(seconds=-10))
    with pytest.raises(Exception):
        decodificar_token(token)
