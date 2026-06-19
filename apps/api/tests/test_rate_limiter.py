import pytest
from app.core.rate_limiter import janela_truncada
from datetime import datetime, timezone

def test_janela_minuto():
    dt = datetime(2026, 5, 29, 14, 32, 47, tzinfo=timezone.utc)
    assert janela_truncada(dt, "minuto") == datetime(2026, 5, 29, 14, 32, 0, tzinfo=timezone.utc)

def test_janela_dia():
    dt = datetime(2026, 5, 29, 14, 32, 47, tzinfo=timezone.utc)
    assert janela_truncada(dt, "dia") == datetime(2026, 5, 29, 0, 0, 0, tzinfo=timezone.utc)

def test_janela_hora():
    dt = datetime(2026, 5, 29, 14, 32, 47, tzinfo=timezone.utc)
    assert janela_truncada(dt, "hora") == datetime(2026, 5, 29, 14, 0, 0, tzinfo=timezone.utc)
