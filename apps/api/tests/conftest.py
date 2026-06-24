import os
import json
import pytest


@pytest.fixture(autouse=True, scope="session")
def _config_dummy():
    """Garante que get_config() funcione nos testes sem exigir config.json real.
    Só seta se nada foi injetado pelo ambiente (CI/local podem sobrescrever)."""
    if not os.environ.get("APOLO_CONFIG_JSON") and not os.environ.get("APOLO_CONFIG_B64"):
        os.environ["APOLO_CONFIG_JSON"] = json.dumps({
            "jwt_secret": "x", "anthropic_api_key": "x", "openai_api_key": "x",
            "crm_conn": "x", "cr_conn": "x", "historico_conn": "x",
        })
    yield
