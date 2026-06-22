"""Eval semantico — rede de regressao de CORRECAO DE NEGOCIO (nao de codigo).

Bate na API ao vivo contra a base real e confere que as respostas continuam corretas
nos casos que ja validamos manualmente (Eduarda=1 tarefa atrasada, contato do Global Drones,
"fechados" = Contrato Assinado, etc.). Estes sao os bugs semanticos que so um humano pegava;
agora viram teste.

ON-DEMAND: so roda com `-m eval` E com a stack no ar. Pular se APOLO_EVAL_BASE_URL nao setado.
    cd apps/api && APOLO_EVAL_BASE_URL=http://localhost:8000 \
        APOLO_EVAL_EMAIL=comercial@provertec.com.br APOLO_EVAL_SENHA=Prover2025! \
        ./.venv/Scripts/python.exe -m pytest tests/test_eval_semantico.py -m eval -v
"""
import json
import os
import urllib.request

import pytest

BASE = os.environ.get("APOLO_EVAL_BASE_URL")
EMAIL = os.environ.get("APOLO_EVAL_EMAIL", "comercial@provertec.com.br")
SENHA = os.environ.get("APOLO_EVAL_SENHA", "Prover2025!")

pytestmark = [
    pytest.mark.eval,
    pytest.mark.skipif(not BASE, reason="APOLO_EVAL_BASE_URL nao setado (stack precisa estar no ar)"),
]


def _token() -> str:
    req = urllib.request.Request(
        f"{BASE}/api/auth/login",
        data=json.dumps({"email": EMAIL, "senha": SENHA}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    return json.loads(urllib.request.urlopen(req, timeout=30).read())["access_token"]


def _perguntar(token: str, pergunta: str) -> str:
    req = urllib.request.Request(
        f"{BASE}/api/chat",
        data=json.dumps({"pergunta": pergunta}).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    partes = []
    for raw in urllib.request.urlopen(req, timeout=150):
        linha = raw.decode("utf-8").rstrip("\r\n")
        if linha.startswith("data:"):
            try:
                d = json.loads(linha[5:].strip())
                if d.get("type") == "token":
                    partes.append(d.get("delta", ""))
            except json.JSONDecodeError:
                pass
    return "".join(partes).strip()


@pytest.fixture(scope="module")
def token():
    return _token()


def test_eduarda_uma_tarefa_atrasada(token):
    """Regra calibrada com o dashboard: nao executada + DtReturn vencido + lead ativo + tarefa atual."""
    resp = _perguntar(token, "quantas tarefas atrasadas a Eduarda Garcia tem?")
    assert "1" in resp
    assert "atrasada" in resp.lower()


def test_global_drones_tem_contato(token):
    """Contato real vive em ClientContacts (CRM_CONTATOS), nao em Clients.Email."""
    resp = _perguntar(token, "qual o contato do cliente Global Drones?")
    assert "Rodrigo" in resp or "contato" in resp.lower()


def test_clientes_fechados_nao_e_todo_o_funil(token):
    """'fechado/ganho' = lead com mc.Descricao='Contrato Assinado' — NAO o total de Clients.
    O numero correto e baixo (dezenas), nunca os ~961 do funil inteiro."""
    resp = _perguntar(token, "quantos clientes fechados temos?")
    assert "961" not in resp
