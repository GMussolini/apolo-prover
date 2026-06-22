# Refatoração de Arquitetura — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decompor as duas funções-deus do APOLO (`engine.py` ~350 linhas e `ChatPanel.tsx` 435 linhas) em estágios pequenos e testáveis, sob uma rede de testes de caracterização que prova comportamento idêntico — sem nenhuma funcionalidade nova.

**Architecture:** Pipeline linear de estágios + `TurnContext` tipado + ports (interfaces) só nas dependências externas (LLM, exec SQL, persistência), com uma política única de erro/persistência no orquestrador. Frontend espelha: transporte SSE em `lib/sse.ts`, estado em hooks (`useChatTurn`, `useVoiceCall`), `ChatPanel` vira composição fina.

**Tech Stack:** Python 3.12 · FastAPI · sse-starlette · pytest · pandas. Next.js 15 · React 19 · TypeScript · Vitest (novo, só para teste).

## Global Constraints

- **ZERO funcionalidade nova.** Nada de estágio novo, endpoint novo, domínio novo, mudança de UI.
- **Comportamento observável idêntico:** mesma sequência de eventos SSE no fio, byte-a-byte, para toda pergunta. Esta é a invariante verificada pela rede.
- **Preservar a INCONSISTÊNCIA atual de erro:** rate-limit e classificador emitem evento `type:"error"`; *todos os demais erros* emitem a mensagem amigável como `type:"token"` (deltas de 40 chars) seguida de `done`. NÃO unificar — reproduzir exatamente. (Unificação fica como backlog.)
- **Preservar os 3 formatos do evento `done`:** (a) só `latencia_ms`; (b) `latencia_ms`+`tokens`; (c) `latencia_ms`+`tokens`+`custo_usd`. Omitir chaves quando a fonte omite.
- **Não tocar:** `domains/*`, `sql_guard.py` (lógica), schema do banco, contrato HTTP, formato SSE no fio.
- **Retry/backoff:** fora do escopo (backlog).
- Cada fase termina com a suíte verde e um commit. Trabalho na branch `arch/refatoracao-orquestrador`; `main` intocado até o merge.

---

## File Structure

**Backend — novo:**
- `apps/api/app/ports/__init__.py` — agrega os ports
- `apps/api/app/ports/llm.py` — `LLMPort` (Protocol) + `AnthropicAdapter`
- `apps/api/app/ports/sql_exec.py` — `SqlExecPort` (Protocol) + `SqlAdapter`
- `apps/api/app/ports/turn_store.py` — `TurnStorePort` (Protocol) + `PgTurnStore`
- `apps/api/app/pipeline/__init__.py`
- `apps/api/app/pipeline/context.py` — `TurnContext`
- `apps/api/app/pipeline/events.py` — eventos tipados + `to_wire()`
- `apps/api/app/pipeline/errors.py` — `ApoloError` + subclasses + `TurnFinished`
- `apps/api/app/pipeline/deps.py` — `Deps` (agrega ports + config)
- `apps/api/app/pipeline/orchestrator.py` — `processar_pergunta` (novo, fino)
- `apps/api/app/pipeline/stages/*.py` — `rate_limit, history, classify, authorize, generate_sql, assemble_sql, execute_sql, answer`
- `apps/api/app/pipeline/sql_builder.py` — recebe `montar_sql_final` (movido de `services/pipeline.py`)

**Backend — modificado:**
- `apps/api/app/core/engine.py` — esvaziado; vira shim que reexporta `pipeline.orchestrator.processar_pergunta` (mantém import de `chat_routes` e `voice_routes`)
- `apps/api/app/services/pipeline.py` — perde `montar_sql_final` (vai pra `sql_builder`); mantém os renderizadores de prompt
- `apps/api/app/Dockerfile` — test stage roda a suíte de caracterização também

**Backend — novo (testes):**
- `apps/api/tests/fakes.py` — fakes dos ports
- `apps/api/tests/fixtures/turns/*.json` — cenários gravados (LLM + SQL + eventos esperados)
- `apps/api/tests/test_characterization.py` — snapshot da sequência de eventos
- `apps/api/tests/test_pipeline_context.py`, `test_pipeline_events.py`, `test_pipeline_errors.py`, `test_ports.py`, `test_stages_*.py`

**Frontend — novo:**
- `apps/web/lib/sse.ts` — `streamSSE` (async-iterator tipado)
- `apps/web/lib/chat-events.ts` — união de tipos `ApoloEvent`
- `apps/web/hooks/useChatTurn.ts`
- `apps/web/hooks/useVoiceCall.ts`
- `apps/web/components/PipelineSteps.tsx`, `Composer.tsx`
- `apps/web/vitest.config.ts`, `apps/web/test/*.test.ts`

**Frontend — modificado:**
- `apps/web/lib/api.ts` — `chatStream` passa a delegar a `lib/sse.ts`
- `apps/web/components/ChatPanel.tsx` — vira composição fina
- `apps/web/package.json` — devDeps de teste + script `test`

---

## FASE 0 — Rede de segurança (caracterização do backend)

> Esta fase NÃO altera nenhuma linha de produção. Captura o comportamento atual.

### Task 0.1: Fakes dos ports e harness de drive do engine atual

**Files:**
- Create: `apps/api/tests/fakes.py`
- Create: `apps/api/tests/conftest.py` (se não existir; senão modificar)
- Test: `apps/api/tests/test_characterization.py`

**Interfaces:**
- Produces:
  - `FakeLLM(roteiro: list[dict])` com método assíncrono `chat_json(modelo, system, user, max_tokens, temperatura) -> dict` e `chat_texto(...) -> dict`, retornando entradas do `roteiro` em ordem (FIFO). Cada entrada: `{"data": {...}, "tokens_input": int, "tokens_output": int}` ou `{"texto": str, ...}`. Se `entry.get("raise")` for verdadeiro, levanta `RuntimeError(entry["raise"])`.
  - `FakeSql(resultado: list[dict] | Exception)` com `execute_query(base, sql, params=None, timeout=30) -> pd.DataFrame`. Se for `Exception`, levanta.
  - `FakeStore()` com `load_history(sessao_id, limite) -> list[tuple[str,str]]` (config via `historico`) e `save_turn(**kwargs) -> None` (grava em `self.saved`).
  - `coletar_eventos(agen) -> list[dict]` — consome um async-generator e devolve a lista de dicts emitidos.

- [ ] **Step 1: Escrever os fakes**

```python
# apps/api/tests/fakes.py
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
```

- [ ] **Step 2: Confirmar que importa**

Run: `cd apps/api && python -c "import tests.fakes; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/fakes.py
git commit -m "test: fakes dos ports para caracterizacao"
```

### Task 0.2: Snapshot de caracterização do engine atual

> Drive o `engine.processar_pergunta` ATUAL injetando os fakes via monkeypatch nos módulos que ele usa hoje (`anthropic_service`, `database.execute_query`, e o pool PG para histórico/persistência). Capturar a sequência de eventos para cenários representativos e congelá-la como snapshot.

**Files:**
- Create: `apps/api/tests/fixtures/turns/contagem_simples.json`
- Create: `apps/api/tests/fixtures/turns/baixa_confianca.json`
- Create: `apps/api/tests/fixtures/turns/permissao_negada.json`
- Create: `apps/api/tests/fixtures/turns/sql_bloqueado.json`
- Create: `apps/api/tests/fixtures/turns/erro_execucao.json`
- Create: `apps/api/tests/fixtures/turns/classificador_falhou.json`
- Create: `apps/api/tests/fixtures/turns/voz_ok.json`
- Modify: `apps/api/tests/test_characterization.py`

**Interfaces:**
- Consumes: `FakeLLM`, `FakeSql`, `FakeStore`, `coletar_eventos` de `tests.fakes`.
- Each fixture JSON tem a forma:
  ```json
  {
    "usuario": {"id": 1, "permissoes": "", "is_admin": true},
    "sessao_id": "s1", "pergunta": "...", "canal": "texto",
    "historico": [],
    "llm": [ {"data": {"dominio": "...", "confidence": 0.9, "pergunta_reformulada": "..."}, "tokens_input": 10, "tokens_output": 5}, ... ],
    "sql_result": [ {"col": "val"} ],
    "sql_raise": null,
    "eventos_esperados": [ {"type": "status", "text": "Entendendo sua pergunta..."}, ... ]
  }
  ```
  (`sql_raise`: string → `FakeSql` levanta `RuntimeError`.)

- [ ] **Step 1: Escrever o teste que roda o engine atual com fakes e compara ao snapshot**

```python
# apps/api/tests/test_characterization.py
import json
import asyncio
from pathlib import Path
import pytest

from tests.fakes import FakeLLM, FakeSql, FakeStore, coletar_eventos

FIX = Path(__file__).parent / "fixtures" / "turns"
CASOS = sorted(p.stem for p in FIX.glob("*.json"))


def _carregar(nome):
    return json.loads((FIX / f"{nome}.json").read_text(encoding="utf-8"))


async def _rodar(caso, monkeypatch):
    from app.core import engine
    from app.services import anthropic_service

    fake_llm = FakeLLM(caso["llm"])
    fake_sql = FakeSql(RuntimeError(caso["sql_raise"]) if caso.get("sql_raise") else caso.get("sql_result", []))
    fake_store = FakeStore(historico=caso.get("historico", []))

    # injeta nas dependências que o engine atual usa
    monkeypatch.setattr(anthropic_service, "chat_json", fake_llm.chat_json)
    monkeypatch.setattr(anthropic_service, "chat_texto", fake_llm.chat_texto)
    monkeypatch.setattr(anthropic_service, "estimar_custo", fake_llm.estimar_custo)
    monkeypatch.setattr(engine, "execute_query", fake_sql.execute_query)
    monkeypatch.setattr(engine, "_carregar_historico", fake_store.load_history)
    monkeypatch.setattr(engine, "_salvar_pergunta_resposta", lambda **kw: fake_store.save_turn(**kw))
    monkeypatch.setattr(engine, "consumir_pergunta", _no_rate_limit)

    eventos = await coletar_eventos(engine.processar_pergunta(
        caso["usuario"], caso["sessao_id"], caso["pergunta"], canal=caso.get("canal", "texto"),
    ))
    return eventos


async def _no_rate_limit(uid):
    return None


def _normalizar(eventos):
    """Remove campos voláteis (latencia_ms) para o snapshot ser determinístico."""
    out = []
    for ev in eventos:
        ev = dict(ev)
        ev.pop("latencia_ms", None)
        out.append(ev)
    return out


@pytest.mark.parametrize("nome", CASOS)
def test_caracterizacao(nome, monkeypatch):
    caso = _carregar(nome)
    eventos = asyncio.run(_rodar(caso, monkeypatch))
    assert _normalizar(eventos) == caso["eventos_esperados"]
```

- [ ] **Step 2: Gerar os esperados a partir do código ATUAL (modo record)**

Rodar um script único que executa cada cenário com o engine atual e grava `eventos_esperados` (já normalizado) no JSON. Criar `apps/api/tests/_gravar_snapshots.py`:

```python
# apps/api/tests/_gravar_snapshots.py — executar UMA vez para gravar o baseline
import json, asyncio
from pathlib import Path
from unittest import mock
from tests.fakes import FakeLLM, FakeSql, FakeStore, coletar_eventos
from tests.test_characterization import _rodar, _normalizar, FIX

for p in sorted(FIX.glob("*.json")):
    caso = json.loads(p.read_text(encoding="utf-8"))
    with mock.patch.object(__import__("pytest"), "skip", lambda *a, **k: None):
        pass
    eventos = asyncio.run(_rodarsem(caso))  # ver nota
    caso["eventos_esperados"] = _normalizar(eventos)
    p.write_text(json.dumps(caso, ensure_ascii=False, indent=2), encoding="utf-8")
    print("gravado", p.stem)
```

> NOTA DE EXECUÇÃO: como `_rodar` recebe `monkeypatch` (fixture pytest), para o modo record use `pytest` com um teste auxiliar marcado, OU refatore `_rodar` para aceitar um objeto com `.setattr`. Caminho mais simples: escreva os `eventos_esperados` manualmente para 1 caso, rode o teste, e use a mensagem de diff do pytest (`assert ==`) para preencher os demais por cópia do "actual". Faça isso cenário a cenário até todos verdes. Os 7 cenários cobrem: sucesso-contagem (texto), baixa confiança, permissão negada, SQL bloqueado, erro de execução, classificador falhou, voz ok.

- [ ] **Step 3: Preencher os 7 fixtures**

Para cada cenário, montar `llm` (o roteiro de respostas do Claude) e `sql_result`/`sql_raise` que levam o engine pelo caminho desejado. Exemplo `contagem_simples.json` (preencher `eventos_esperados` rodando o teste):

```json
{
  "usuario": {"id": 1, "permissoes": "crm", "is_admin": true},
  "sessao_id": "s1", "pergunta": "quantos leads ativos?", "canal": "texto",
  "historico": [],
  "llm": [
    {"data": {"dominio": "CRM_PIPELINE", "confidence": 0.95, "pergunta_reformulada": "quantos leads ativos"}, "tokens_input": 100, "tokens_output": 20},
    {"data": {"wheres": {"prelead": "1=0", "lead": "c.FaseAtivo = 1"}, "select_list": "COUNT(*) AS qtd", "group_by": "", "order_by": "", "top": 500}, "tokens_input": 200, "tokens_output": 30},
    {"data": {"resposta": "Há 42 leads ativos.", "grafico_sugerido": null, "spec_grafico": null}, "tokens_input": 80, "tokens_output": 15}
  ],
  "sql_result": [{"qtd": 42}],
  "sql_raise": null,
  "eventos_esperados": []
}
```

- [ ] **Step 4: Rodar a suíte e confirmar verde com os esperados preenchidos**

Run: `cd apps/api && python -m pytest tests/test_characterization.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add apps/api/tests/test_characterization.py apps/api/tests/fixtures/turns/*.json
git commit -m "test: snapshot de caracterizacao do engine (7 cenarios)"
```

### Task 0.3: Build gate roda a caracterização

**Files:**
- Modify: `apps/api/Dockerfile:26`

- [ ] **Step 1: Ampliar o test stage**

Trocar a linha que roda só o catálogo por:

```dockerfile
RUN python -m pytest tests/test_catalog_consistency.py tests/test_characterization.py -q
```

- [ ] **Step 2: Validar o build do test stage**

Run: `cd apps/api && docker build --target test -t apolo-api-test .`
Expected: build conclui; saída mostra os testes passando.

- [ ] **Step 3: Commit**

```bash
git add apps/api/Dockerfile
git commit -m "ci: build gate roda testes de caracterizacao"
```

---

## FASE 1 — Ports + adapters

> Introduz as interfaces e envolve as dependências atuais. O engine passa a chamar adapters em vez de funções de módulo. Snapshot deve seguir verde.

### Task 1.1: `LLMPort` + `AnthropicAdapter`

**Files:**
- Create: `apps/api/app/ports/__init__.py`
- Create: `apps/api/app/ports/llm.py`
- Test: `apps/api/tests/test_ports.py`

**Interfaces:**
- Produces:
  - `class LLMPort(Protocol)` com `async def chat_json(self, modelo, system, user, max_tokens=1500, temperatura=0.0) -> dict`, `async def chat_texto(self, modelo, system, user, max_tokens=500, temperatura=0.3) -> dict`, `def estimar_custo(self, modelo, ti, to) -> float`.
  - `class AnthropicAdapter` que delega ao módulo `anthropic_service` (comportamento idêntico).

- [ ] **Step 1: Teste — o adapter delega ao service**

```python
# apps/api/tests/test_ports.py
import asyncio
from app.ports.llm import AnthropicAdapter


def test_anthropic_adapter_delega(monkeypatch):
    chamado = {}
    async def fake_chat_json(modelo, system, user, max_tokens=1500, temperatura=0.0):
        chamado["modelo"] = modelo
        return {"data": {"ok": True}, "tokens_input": 1, "tokens_output": 2}
    from app.services import anthropic_service
    monkeypatch.setattr(anthropic_service, "chat_json", fake_chat_json)

    r = asyncio.run(AnthropicAdapter().chat_json("m", "s", "u"))
    assert r["data"] == {"ok": True}
    assert chamado["modelo"] == "m"
```

- [ ] **Step 2: Rodar — falha (módulo não existe)**

Run: `cd apps/api && python -m pytest tests/test_ports.py::test_anthropic_adapter_delega -v`
Expected: FAIL (ModuleNotFoundError app.ports.llm)

- [ ] **Step 3: Implementar**

```python
# apps/api/app/ports/__init__.py
```
```python
# apps/api/app/ports/llm.py
from typing import Protocol
from app.services import anthropic_service


class LLMPort(Protocol):
    async def chat_json(self, modelo: str, system: str, user: str,
                        max_tokens: int = 1500, temperatura: float = 0.0) -> dict: ...
    async def chat_texto(self, modelo: str, system: str, user: str,
                         max_tokens: int = 500, temperatura: float = 0.3) -> dict: ...
    def estimar_custo(self, modelo: str, ti: int, to: int) -> float: ...


class AnthropicAdapter:
    async def chat_json(self, modelo, system, user, max_tokens=1500, temperatura=0.0) -> dict:
        return await anthropic_service.chat_json(modelo, system, user, max_tokens, temperatura)

    async def chat_texto(self, modelo, system, user, max_tokens=500, temperatura=0.3) -> dict:
        return await anthropic_service.chat_texto(modelo, system, user, max_tokens, temperatura)

    def estimar_custo(self, modelo, ti, to) -> float:
        return anthropic_service.estimar_custo(modelo, ti, to)
```

- [ ] **Step 4: Rodar — passa**

Run: `cd apps/api && python -m pytest tests/test_ports.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/ports/__init__.py apps/api/app/ports/llm.py apps/api/tests/test_ports.py
git commit -m "feat: LLMPort + AnthropicAdapter"
```

### Task 1.2: `SqlExecPort` + `SqlAdapter` e `TurnStorePort` + `PgTurnStore`

**Files:**
- Create: `apps/api/app/ports/sql_exec.py`
- Create: `apps/api/app/ports/turn_store.py`
- Modify: `apps/api/tests/test_ports.py`

**Interfaces:**
- Produces:
  - `class SqlExecPort(Protocol)`: `async def execute_query(self, base, sql, params=None, timeout=30) -> pd.DataFrame`.
  - `class SqlAdapter` delegando a `database.execute_query`.
  - `class TurnStorePort(Protocol)`: `async def load_history(self, sessao_id, limite=5) -> list[tuple[str,str]]`, `async def save_turn(self, **kwargs) -> None`.
  - `class PgTurnStore` que move a lógica de `_carregar_historico` e `_salvar_pergunta_resposta` do engine (cópia verbatim das duas funções, agora como métodos).

- [ ] **Step 1: Teste — SqlAdapter delega**

```python
# adicionar em apps/api/tests/test_ports.py
import pandas as pd
from app.ports.sql_exec import SqlAdapter

def test_sql_adapter_delega(monkeypatch):
    async def fake_exec(base, sql, params=None, timeout=30):
        return pd.DataFrame([{"x": 1}])
    from app.core import database
    monkeypatch.setattr(database, "execute_query", fake_exec)
    df = asyncio.run(SqlAdapter().execute_query("crm", "SELECT 1"))
    assert df.iloc[0]["x"] == 1
```

- [ ] **Step 2: Rodar — falha**

Run: `cd apps/api && python -m pytest tests/test_ports.py::test_sql_adapter_delega -v`
Expected: FAIL

- [ ] **Step 3: Implementar os dois ports**

```python
# apps/api/app/ports/sql_exec.py
from typing import Protocol
import pandas as pd
from app.core import database


class SqlExecPort(Protocol):
    async def execute_query(self, base: str, sql: str, params: dict | None = None,
                           timeout: int = 30) -> pd.DataFrame: ...


class SqlAdapter:
    async def execute_query(self, base, sql, params=None, timeout=30) -> pd.DataFrame:
        return await database.execute_query(base, sql, params, timeout)
```

```python
# apps/api/app/ports/turn_store.py
import json
from typing import Protocol
from app.core.database import get_pg_pool


class TurnStorePort(Protocol):
    async def load_history(self, sessao_id: str, limite: int = 5) -> list[tuple[str, str]]: ...
    async def save_turn(self, **kwargs) -> None: ...


class PgTurnStore:
    async def load_history(self, sessao_id: str, limite: int = 5) -> list[tuple[str, str]]:
        # MOVER aqui o corpo de engine._carregar_historico (verbatim)
        ...

    async def save_turn(self, **kwargs) -> None:
        # MOVER aqui o corpo de engine._salvar_pergunta_resposta (verbatim),
        # lendo os campos de kwargs com os mesmos nomes atuais.
        ...
```

> IMPORTANTE: copiar o corpo EXATO das funções `_carregar_historico` e `_salvar_pergunta_resposta` de `engine.py` (linhas 36-56 e 92-158). Não reescrever a SQL.

- [ ] **Step 4: Teste — PgTurnStore.save_turn monta o mesmo INSERT (com pool fake)**

```python
# adicionar em test_ports.py — verifica que chama execute com os campos certos
class _FakeCur:
    def __init__(self): self.execs = []
    async def execute(self, sql, params=None): self.execs.append((sql, params))
    async def fetchone(self): return (123,)
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
class _FakeConn:
    def __init__(self, cur): self._cur = cur
    def cursor(self): return self._cur
    async def commit(self): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
class _FakePool:
    def __init__(self, conn): self._conn = conn
    def connection(self): return self._conn

def test_pg_turn_store_save(monkeypatch):
    cur = _FakeCur(); pool = _FakePool(_FakeConn(cur))
    from app.ports import turn_store
    monkeypatch.setattr(turn_store, "get_pg_pool", lambda: pool)
    from app.ports.turn_store import PgTurnStore
    asyncio.run(PgTurnStore().save_turn(
        sessao_id="s1", usuario_id=1, pergunta="p", pergunta_reformulada="p",
        dominio_nome="D", base_conexao="crm", confidence=0.9, canal="texto",
        resposta_texto="r", sql_gerado="SELECT 1", dados_retornados=[{"a":1}],
        grafico_sugerido=None, spec_grafico=None, tokens_input=1, tokens_output=2,
        custo_estimado=0.0, latencia_ms=10, erro=None))
    assert any("INSERT INTO tb_pergunta" in e[0] for e in cur.execs)
    assert any("INSERT INTO tb_resposta" in e[0] for e in cur.execs)
```

- [ ] **Step 5: Rodar — passa**

Run: `cd apps/api && python -m pytest tests/test_ports.py -v`
Expected: PASS (todos)

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/ports/sql_exec.py apps/api/app/ports/turn_store.py apps/api/tests/test_ports.py
git commit -m "feat: SqlExecPort + TurnStorePort com adapters"
```

### Task 1.3: `Deps` e engine consumindo os ports

**Files:**
- Create: `apps/api/app/pipeline/__init__.py`
- Create: `apps/api/app/pipeline/deps.py`
- Modify: `apps/api/app/core/engine.py` (trocar chamadas diretas por `deps.*`)

**Interfaces:**
- Produces: `@dataclass class Deps: llm: LLMPort; sql: SqlExecPort; store: TurnStorePort; cfg: Config`. Função `default_deps() -> Deps` instanciando os adapters reais.
- Consumes (no engine): substituir `anthropic_service.chat_json(...)` → `deps.llm.chat_json(...)`; `execute_query(...)` → `deps.sql.execute_query(...)`; `_carregar_historico(...)` → `deps.store.load_history(...)`; `_salvar_pergunta_resposta(...)` → `deps.store.save_turn(...)`; `anthropic_service.estimar_custo` → `deps.llm.estimar_custo`.

- [ ] **Step 1: Implementar Deps**

```python
# apps/api/app/pipeline/__init__.py
```
```python
# apps/api/app/pipeline/deps.py
from dataclasses import dataclass
from app.core.config import Config, get_config
from app.ports.llm import LLMPort, AnthropicAdapter
from app.ports.sql_exec import SqlExecPort, SqlAdapter
from app.ports.turn_store import TurnStorePort, PgTurnStore


@dataclass
class Deps:
    llm: LLMPort
    sql: SqlExecPort
    store: TurnStorePort
    cfg: Config


def default_deps() -> Deps:
    return Deps(llm=AnthropicAdapter(), sql=SqlAdapter(), store=PgTurnStore(), cfg=get_config())
```

- [ ] **Step 2: Alterar `processar_pergunta` para criar `deps` e usar**

No topo de `processar_pergunta`: `deps = default_deps()`. Substituir cada chamada externa pelos métodos de `deps` (ver Interfaces). Remover `_carregar_historico`/`_salvar_pergunta_resposta`/`_format_historico`? — manter `_format_historico` (puro), mover history/save para o store. `_persistir` passa a chamar `deps.store.save_turn(...)`.

> O teste de caracterização (Fase 0) agora precisa injetar via `deps`. Atualizar `test_characterization._rodar` para fazer monkeypatch de `app.pipeline.deps.default_deps` retornando um `Deps(FakeLLM, FakeSql, FakeStore, get_config())`. Ajustar e confirmar verde.

- [ ] **Step 3: Atualizar o harness de caracterização para injetar Deps**

```python
# em test_characterization._rodar, substituir os monkeypatch antigos por:
from app.pipeline.deps import Deps
from app.core.config import get_config
deps = Deps(llm=fake_llm, sql=fake_sql, store=fake_store, cfg=get_config())
monkeypatch.setattr("app.pipeline.deps.default_deps", lambda: deps)
monkeypatch.setattr(engine, "consumir_pergunta", _no_rate_limit)
```

> `get_config()` exige `config.json` ou env. No CI o test stage tem `config.example.json`? Garantir um `APOLO_CONFIG_JSON` mínimo via `conftest.py` (fixture autouse que seta env com chaves dummy) para `get_config()` não falhar. Adicionar:

```python
# apps/api/tests/conftest.py
import os, json, pytest

@pytest.fixture(autouse=True, scope="session")
def _config_dummy():
    if not os.environ.get("APOLO_CONFIG_JSON"):
        os.environ["APOLO_CONFIG_JSON"] = json.dumps({
            "jwt_secret": "x", "anthropic_api_key": "x", "openai_api_key": "x",
            "crm_conn": "x", "cr_conn": "x", "postgres_conn": "x",
        })
    yield
```

- [ ] **Step 4: Rodar a caracterização — segue verde**

Run: `cd apps/api && python -m pytest tests/test_characterization.py tests/test_ports.py -v`
Expected: todos PASS (comportamento idêntico)

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/pipeline/ apps/api/app/core/engine.py apps/api/tests/conftest.py apps/api/tests/test_characterization.py
git commit -m "refactor: engine consome ports via Deps (comportamento identico)"
```

---

## FASE 2 — TurnContext + events + errors

### Task 2.1: `TurnContext`

**Files:**
- Create: `apps/api/app/pipeline/context.py`
- Test: `apps/api/tests/test_pipeline_context.py`

**Interfaces:**
- Produces: `@dataclass class TurnContext` com campos: `usuario: dict`, `sessao_id: str`, `pergunta: str`, `canal: str`, `t0: float`, e mutáveis `tokens_input=0`, `tokens_output=0`, `custo=0.0`, `pergunta_reformulada=None`, `dominio_nome=None`, `base_conexao=None`, `confidence=None`, `sql_gerado=None`, `dados_retornados=None`, `resposta_texto=None`, `grafico_sugerido=None`, `spec_grafico=None`, `erro=None`. Métodos: `add_usage(ti, to, custo)`, `latencia_ms() -> int`, `tokens_dict() -> dict`, `save_kwargs() -> dict` (monta o dict exato que `save_turn` espera).

- [ ] **Step 1: Teste**

```python
# apps/api/tests/test_pipeline_context.py
import time
from app.pipeline.context import TurnContext

def test_add_usage_e_save_kwargs():
    ctx = TurnContext(usuario={"id": 7}, sessao_id="s", pergunta="p", canal="texto", t0=time.perf_counter())
    ctx.add_usage(10, 5, 0.001)
    ctx.add_usage(20, 3, 0.002)
    assert ctx.tokens_input == 30 and ctx.tokens_output == 8
    assert round(ctx.custo, 3) == 0.003
    ctx.dominio_nome = "CRM_PIPELINE"
    kw = ctx.save_kwargs()
    assert kw["usuario_id"] == 7
    assert kw["dominio_nome"] == "CRM_PIPELINE"
    assert kw["tokens_input"] == 30 and kw["tokens_output"] == 8
    assert "latencia_ms" in kw
```

- [ ] **Step 2: Rodar — falha** · Run: `cd apps/api && python -m pytest tests/test_pipeline_context.py -v` · Expected: FAIL

- [ ] **Step 3: Implementar**

```python
# apps/api/app/pipeline/context.py
import time
from dataclasses import dataclass, field


@dataclass
class TurnContext:
    usuario: dict
    sessao_id: str
    pergunta: str
    canal: str
    t0: float
    tokens_input: int = 0
    tokens_output: int = 0
    custo: float = 0.0
    pergunta_reformulada: str | None = None
    dominio_nome: str | None = None
    base_conexao: str | None = None
    confidence: float | None = None
    sql_gerado: str | None = None
    dados_retornados: list | None = None
    resposta_texto: str | None = None
    grafico_sugerido: str | None = None
    spec_grafico: dict | None = None
    erro: str | None = None

    def add_usage(self, ti: int, to: int, custo: float) -> None:
        self.tokens_input += ti
        self.tokens_output += to
        self.custo += custo

    def latencia_ms(self) -> int:
        return int((time.perf_counter() - self.t0) * 1000)

    def tokens_dict(self) -> dict:
        return {"input": self.tokens_input, "output": self.tokens_output}

    def save_kwargs(self) -> dict:
        return {
            "sessao_id": self.sessao_id,
            "usuario_id": self.usuario["id"],
            "pergunta": self.pergunta,
            "pergunta_reformulada": self.pergunta_reformulada,
            "dominio_nome": self.dominio_nome,
            "base_conexao": self.base_conexao,
            "confidence": round(self.confidence, 2) if self.confidence is not None else None,
            "canal": self.canal,
            "resposta_texto": self.resposta_texto,
            "sql_gerado": self.sql_gerado,
            "dados_retornados": self.dados_retornados,
            "grafico_sugerido": self.grafico_sugerido,
            "spec_grafico": self.spec_grafico,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "custo_estimado": round(self.custo, 6),
            "latencia_ms": self.latencia_ms(),
            "erro": self.erro,
        }
```

- [ ] **Step 4: Rodar — passa** · Expected: PASS
- [ ] **Step 5: Commit** · `git add ... && git commit -m "feat: TurnContext"`

### Task 2.2: `events.py` reproduzindo os dicts atuais byte-a-byte

**Files:**
- Create: `apps/api/app/pipeline/events.py`
- Test: `apps/api/tests/test_pipeline_events.py`

**Interfaces:**
- Produces classes com `to_wire() -> dict`:
  - `Status(text)` → `{"type":"status","text":text}`
  - `Classification(dominio, confidence)` → `{"type":"classification","dominio":dominio,"confidence":confidence}`
  - `Sql(sql)` → `{"type":"sql","sql":sql}`
  - `Token(delta)` → `{"type":"token","delta":delta}`
  - `Chart(tipo, spec)` → `{"type":"chart","tipo":tipo,"spec":spec}`
  - `ErrorEvent(text)` → `{"type":"error","text":text}`
  - `Done(latencia_ms, tokens=None, custo_usd=None)` → inclui `tokens` só se não-None, `custo_usd` só se não-None.

- [ ] **Step 1: Teste cobrindo os 3 formatos de `done` e o omitir-quando-None**

```python
# apps/api/tests/test_pipeline_events.py
from app.pipeline.events import Status, Classification, Sql, Token, Chart, ErrorEvent, Done

def test_eventos_simples():
    assert Status("oi").to_wire() == {"type": "status", "text": "oi"}
    assert Token("ab").to_wire() == {"type": "token", "delta": "ab"}
    assert Sql("SELECT 1").to_wire() == {"type": "sql", "sql": "SELECT 1"}
    assert ErrorEvent("x").to_wire() == {"type": "error", "text": "x"}
    assert Classification("D", 0.9).to_wire() == {"type": "classification", "dominio": "D", "confidence": 0.9}
    assert Chart("bar", {"a": 1}).to_wire() == {"type": "chart", "tipo": "bar", "spec": {"a": 1}}

def test_done_tres_formatos():
    assert Done(10).to_wire() == {"type": "done", "latencia_ms": 10}
    assert Done(10, tokens={"input": 1, "output": 2}).to_wire() == {
        "type": "done", "latencia_ms": 10, "tokens": {"input": 1, "output": 2}}
    assert Done(10, tokens={"input": 1, "output": 2}, custo_usd=0.5).to_wire() == {
        "type": "done", "latencia_ms": 10, "tokens": {"input": 1, "output": 2}, "custo_usd": 0.5}
```

- [ ] **Step 2: Rodar — falha** · Expected: FAIL
- [ ] **Step 3: Implementar**

```python
# apps/api/app/pipeline/events.py
from dataclasses import dataclass


@dataclass
class Status:
    text: str
    def to_wire(self): return {"type": "status", "text": self.text}

@dataclass
class Classification:
    dominio: str
    confidence: float
    def to_wire(self): return {"type": "classification", "dominio": self.dominio, "confidence": self.confidence}

@dataclass
class Sql:
    sql: str
    def to_wire(self): return {"type": "sql", "sql": self.sql}

@dataclass
class Token:
    delta: str
    def to_wire(self): return {"type": "token", "delta": self.delta}

@dataclass
class Chart:
    tipo: str
    spec: dict
    def to_wire(self): return {"type": "chart", "tipo": self.tipo, "spec": self.spec}

@dataclass
class ErrorEvent:
    text: str
    def to_wire(self): return {"type": "error", "text": self.text}

@dataclass
class Done:
    latencia_ms: int
    tokens: dict | None = None
    custo_usd: float | None = None
    def to_wire(self):
        d = {"type": "done", "latencia_ms": self.latencia_ms}
        if self.tokens is not None:
            d["tokens"] = self.tokens
        if self.custo_usd is not None:
            d["custo_usd"] = self.custo_usd
        return d
```

- [ ] **Step 4: Rodar — passa** · Expected: PASS
- [ ] **Step 5: Commit** · `git commit -m "feat: eventos tipados com to_wire (preserva dicts atuais)"`

### Task 2.3: `errors.py` — taxonomia + sinal de controle

**Files:**
- Create: `apps/api/app/pipeline/errors.py`
- Test: `apps/api/tests/test_pipeline_errors.py`

**Interfaces:**
- Produces:
  - `class TurnFinished(Exception)` — sinal de short-circuit "resposta já emitida" (não é erro).
  - `class ApoloError(Exception)`: atributos `mensagem_amigavel: str`, `codigo_log: str`, `modo: Literal["error_event","token_stream"]`. Construtor `(mensagem_amigavel, codigo_log, modo, causa=None)`.
  - Subclasses-fábrica que fixam o `modo` e a mensagem para reproduzir o comportamento atual:
    - `RateLimited(detail)` → modo `error_event`, msg=`detail`, codigo=`rate_limit`
    - `ClassifyFailed(causa)` → modo `error_event`, msg=`"Não consegui entender sua pergunta. Tente reformular."`, codigo=`classificador`
    - `SqlGenFailed` → modo `token_stream`, msg=`"Tive um problema gerando a consulta. Tente reformular a pergunta."`
    - `SqlBlocked` → modo `token_stream`, msg=`"A consulta gerada foi bloqueada por segurança. Tente reformular."`
    - `SqlBuildFailed` → modo `token_stream`, msg=`"Não consegui montar a consulta. Tente reformular."`
    - `SqlExecFailed` → modo `token_stream`, msg=`"Não consegui consultar a base no momento. Tente de novo em instantes."`
    - `AnswerFailed(canal)` → modo `token_stream`, msg conforme canal (voz: `"Consegui os dados, mas falhei em narrar. Tente de novo."`; texto: `"Consegui os dados, mas falhei em formatar a resposta. Tente de novo."`)

> As mensagens são CÓPIA EXATA das strings atuais de `engine.py`. Conferir caractere a caractere.

- [ ] **Step 1: Teste**

```python
# apps/api/tests/test_pipeline_errors.py
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
```

- [ ] **Step 2: Rodar — falha** · Expected: FAIL
- [ ] **Step 3: Implementar** (copiar strings de engine.py linhas 265, 346, 366, 376, 401, 435, 474)

```python
# apps/api/app/pipeline/errors.py
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
        super().__init__(str(detail), "rate_limit", "error_event")

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
```

- [ ] **Step 4: Rodar — passa** · Expected: PASS
- [ ] **Step 5: Commit** · `git commit -m "feat: taxonomia de erros + TurnFinished"`

---

## FASE 3 — Estágios (mover um a um, snapshot verde a cada passo)

> Padrão de cada estágio: função `async def run(ctx: TurnContext, deps: Deps) -> AsyncIterator[Event]`.
> Estágios podem `yield` eventos, mutar `ctx`, levantar `ApoloError` (erro) ou `TurnFinished` (short-circuit).
> O `_chunk_text` (engine.py:71-76) vai para `pipeline/stages/_util.py` e é reusado.
> APÓS cada task desta fase: `python -m pytest tests/test_characterization.py -q` DEVE ficar verde.

### Task 3.0: util compartilhado + esqueleto do orquestrador novo (paralelo ao atual)

**Files:**
- Create: `apps/api/app/pipeline/stages/__init__.py`
- Create: `apps/api/app/pipeline/stages/_util.py` (move `_chunk_text`)
- Create: `apps/api/app/pipeline/orchestrator.py` (inicialmente delega ao engine atual)

- [ ] **Step 1:** Mover `_chunk_text` para `_util.py` (cópia verbatim de engine.py:71-76); `engine.py` importa de lá.
- [ ] **Step 2:** Criar `orchestrator.processar_pergunta` que, por ora, apenas chama `engine.processar_pergunta` (re-export). Isso permite migrar `chat_routes`/`voice_routes` o import depois sem mudar comportamento.
- [ ] **Step 3:** Caracterização verde · Run: `python -m pytest tests/test_characterization.py -q`
- [ ] **Step 4:** Commit · `git commit -m "refactor: util compartilhado + esqueleto do orquestrador"`

### Tasks 3.1–3.8: extrair cada estágio

Para CADA estágio abaixo, o procedimento é idêntico:

1. Criar `apps/api/app/pipeline/stages/<nome>.py` com `async def run(ctx, deps)` contendo o bloco correspondente de `engine.processar_pergunta`, traduzido para: `yield` de objetos de `events.py` (não dicts), mutação de `ctx` (não `estado`), e `raise ApoloError/TurnFinished` no lugar dos early-returns.
2. Escrever teste unitário do estágio em `tests/test_stages_<nome>.py` com `FakeLLM/FakeSql/FakeStore` cobrindo o caminho feliz e o(s) de erro.
3. Rodar o teste do estágio (verde).
4. Ligar o estágio no `orchestrator.py` (substituindo o trecho equivalente) e rodar a caracterização (verde).
5. Commit.

Estágios, na ordem, com a fonte exata em `engine.py`:

| Task | Estágio | Fonte (engine.py) | Erros/short-circuits |
|---|---|---|---|
| 3.1 | `rate_limit.run` | linhas 224-231 | `RateLimited` (error_event) |
| 3.2 | `history.run` | 238-239 | (sem erro; seta `ctx` via `deps.store.load_history` + `_format_historico`) |
| 3.3 | `classify.run` | 244-301 | `ClassifyFailed` (error_event); baixa confiança/domínio inválido → emite tokens do refinamento + `TurnFinished` |
| 3.4 | `authorize.run` | 306-325 | permissão negada → emite tokens + seta `ctx.erro="permissao_negada"` + `TurnFinished` |
| 3.5 | `generate_sql.run` | 332-358 | `SqlGenFailed` (token_stream) |
| 3.6 | `assemble_sql.run` | 360-385 | `SqlBlocked`/`SqlBuildFailed` (token_stream); usa `sql_builder.montar_sql_final` |
| 3.7 | `execute_sql.run` | 390-412 | `SqlExecFailed` (token_stream) |
| 3.8 | `answer.run` | 414-501 | `AnswerFailed` (token_stream); ramifica por `ctx.canal` |

**Exemplo concreto — Task 3.1 (rate_limit):**

- [ ] **Step 1: Estágio**

```python
# apps/api/app/pipeline/stages/rate_limit.py
from fastapi import HTTPException
from app.core.rate_limiter import consumir_pergunta
from app.pipeline.errors import RateLimited


async def run(ctx, deps):
    try:
        await consumir_pergunta(ctx.usuario["id"])
    except HTTPException as e:
        raise RateLimited(e.detail)
    return
    yield  # marca como async-generator
```

- [ ] **Step 2: Teste**

```python
# apps/api/tests/test_stages_rate_limit.py
import asyncio, pytest
from fastapi import HTTPException
from app.pipeline.stages import rate_limit
from app.pipeline.errors import RateLimited
from app.pipeline.context import TurnContext
import time

def _ctx():
    return TurnContext(usuario={"id": 1}, sessao_id="s", pergunta="p", canal="texto", t0=time.perf_counter())

def test_rate_limit_ok(monkeypatch):
    async def ok(uid): return None
    monkeypatch.setattr(rate_limit, "consumir_pergunta", ok)
    evs = asyncio.run(_coletar(rate_limit.run(_ctx(), None)))
    assert evs == []

def test_rate_limit_estoura(monkeypatch):
    async def estoura(uid): raise HTTPException(status_code=429, detail="limite diário")
    monkeypatch.setattr(rate_limit, "consumir_pergunta", estoura)
    with pytest.raises(RateLimited) as ei:
        asyncio.run(_coletar(rate_limit.run(_ctx(), None)))
    assert ei.value.modo == "error_event"

async def _coletar(agen):
    return [e async for e in agen]
```

- [ ] **Step 3:** Rodar teste do estágio (verde).
- [ ] **Step 4:** Ligar no orquestrador (ver Task 4.1 monta o loop final; aqui só garantir import). Caracterização verde.
- [ ] **Step 5:** Commit `git commit -m "refactor: estagio rate_limit"`

> Repetir o padrão para 3.2–3.8. Cada `yield {"type": ...}` do engine vira `yield <Event>(...)`; cada `estado[k]=v` vira `ctx.k=v`; cada bloco `except ... return` vira `raise <ApoloError>`. Para os caminhos token_stream que hoje fazem `for ch in _chunk_text(msg): yield {"type":"token",...}` ANTES de `done` — isso passa a ser responsabilidade da política do orquestrador (Fase 4), então no estágio basta `raise <ApoloError>`. Para os short-circuits de resposta-normal (baixa confiança, permissão) o estágio emite os `Token` e levanta `TurnFinished`.

### Task 3.9: mover `montar_sql_final` para `sql_builder.py`

**Files:**
- Create: `apps/api/app/pipeline/sql_builder.py`
- Modify: `apps/api/app/services/pipeline.py` (remover `montar_sql_final`, manter renderizadores)
- Modify: imports em `stages/assemble_sql.py`

- [ ] **Step 1:** Mover a função `montar_sql_final` (services/pipeline.py:104-128) verbatim para `sql_builder.py`. Manter `validar_sql_readonly` import.
- [ ] **Step 2:** `assemble_sql.run` importa de `sql_builder`.
- [ ] **Step 3:** Caracterização verde + `test_domains_base` verde.
- [ ] **Step 4:** Commit `git commit -m "refactor: montar_sql_final -> pipeline/sql_builder"`

---

## FASE 4 — Orquestrador fino + política única

### Task 4.1: orquestrador roda estágios e aplica a política única

**Files:**
- Modify: `apps/api/app/pipeline/orchestrator.py`
- Modify: `apps/api/app/core/engine.py` (vira shim de compat)

**Interfaces:**
- Produces: `async def processar_pergunta(usuario, sessao_id, pergunta, canal="texto") -> AsyncIterator[dict]` — assinatura IDÊNTICA à atual; emite dicts via `Event.to_wire()`.

- [ ] **Step 1: Implementar o orquestrador final**

```python
# apps/api/app/pipeline/orchestrator.py
import time
from typing import AsyncGenerator
from app.core.logging_config import logger
from app.pipeline.context import TurnContext
from app.pipeline.deps import default_deps
from app.pipeline.errors import ApoloError, TurnFinished
from app.pipeline.events import Token, ErrorEvent, Done
from app.pipeline.stages import _util
from app.pipeline.stages import (rate_limit, history, classify, authorize,
                                  generate_sql, assemble_sql, execute_sql, answer)

STAGES = [rate_limit, history, classify, authorize, generate_sql, assemble_sql, execute_sql, answer]


async def processar_pergunta(usuario, sessao_id, pergunta, canal="texto") -> AsyncGenerator[dict, None]:
    ctx = TurnContext(usuario=usuario, sessao_id=sessao_id, pergunta=pergunta, canal=canal, t0=time.perf_counter())
    deps = default_deps()
    erro_apolo: ApoloError | None = None
    try:
        for stage in STAGES:
            async for ev in stage.run(ctx, deps):
                yield ev.to_wire()
    except TurnFinished:
        pass
    except ApoloError as e:
        erro_apolo = e
        ctx.erro = e.codigo_log
        logger.error(f"engine.{e.codigo_log}", erro=str(e.causa or e))
        if e.modo == "error_event":
            yield ErrorEvent(e.mensagem_amigavel).to_wire()
        else:  # token_stream
            ctx.resposta_texto = e.mensagem_amigavel
            for ch in _util.chunk_text(e.mensagem_amigavel, 40):
                yield Token(ch).to_wire()
    # persistência: UMA vez
    try:
        await deps.store.save_turn(**ctx.save_kwargs())
    except Exception as e:
        logger.error("engine.persistencia_falhou", erro=str(e))
    # done: formato conforme o caminho
    yield _done_event(ctx, erro_apolo).to_wire()


def _done_event(ctx, erro_apolo) -> Done:
    # Reproduz os 3 formatos atuais:
    # - rate_limit / classificador (error_event) e erros token_stream "cedo": só latencia_ms
    # - baixa confiança / permissão (TurnFinished antes de SQL): latencia_ms + tokens
    # - sucesso e demais com tokens acumulados: latencia_ms + tokens (+ custo_usd no sucesso)
    ...
```

> O `_done_event` precisa reproduzir EXATAMENTE qual `done` cada caminho emite hoje. Mapear pela tabela:
> | Caminho | done atual |
> |---|---|
> | rate_limit | `{latencia_ms}` |
> | classificador falhou | `{latencia_ms}` |
> | baixa confiança | `{latencia_ms, tokens}` |
> | permissão negada | `{latencia_ms, tokens}` |
> | sql_generator/montar/exec/answer falhou | `{latencia_ms}` |
> | sucesso | `{latencia_ms, tokens, custo_usd}` |
>
> Implementar com flags em `ctx` setadas pelos estágios: `ctx.emitir_tokens_no_done` (bool) e `ctx.emitir_custo_no_done` (bool). `classify` seta `emitir_tokens=True` ao chegar em classificação bem-sucedida; `answer` seta `emitir_custo=True` no sucesso. Para os erros token_stream o `done` é só `{latencia_ms}` — garantir que esses caminhos deixem as flags em False (i.e., as flags só ligam após o ponto correspondente). Ajustar até a caracterização ficar verde — o snapshot é a fonte da verdade.

- [ ] **Step 2:** Adicionar `chunk_text` público em `_util.py` (renome de `_chunk_text`).
- [ ] **Step 3:** `engine.py` vira shim:

```python
# apps/api/app/core/engine.py  (conteúdo final)
from app.pipeline.orchestrator import processar_pergunta  # noqa: F401
```

- [ ] **Step 4:** Atualizar `test_characterization` para injetar deps via `app.pipeline.deps.default_deps` (já feito na Fase 1) e dirigir `orchestrator.processar_pergunta`. Rodar:

Run: `cd apps/api && python -m pytest tests/ -q`
Expected: TODOS verdes (caracterização idêntica + unit dos estágios)

- [ ] **Step 5:** Commit `git commit -m "refactor: orquestrador fino com politica unica de erro/persistencia"`

### Task 4.2: apontar rotas para o orquestrador e remover código morto

**Files:**
- Modify: `apps/api/app/api/chat_routes.py:13` (import já resolve via shim; opcional apontar direto)
- Modify: `apps/api/app/api/voice_routes.py` (mesmo)
- Modify: `apps/api/app/core/engine.py` (remover helpers já migrados: `_carregar_historico`, `_salvar_pergunta_resposta`, `_df_para_amostra` se movido para `execute_sql`, etc.)

- [ ] **Step 1:** Garantir que `_df_para_amostra` foi para `stages/execute_sql.py` e `_format_historico` para `stages/history.py`. Remover do engine o que sobrou.
- [ ] **Step 2:** `grep -rn "core.engine" apps/api/app` — confirmar que só o shim resta.
- [ ] **Step 3:** Rodar suíte completa + subir a stack e smoke:

Run: `cd apps/api && python -m pytest tests/ -q` · Expected: verde
Run (stack): `docker compose up --build -d api && <perguntar "quantas tarefas atrasadas a Eduarda Garcia tem?">` · Expected: **1** (idêntico ao pré-refatoração)

- [ ] **Step 4:** Commit `git commit -m "refactor: remove codigo morto do engine; engine vira shim"`

---

## FASE 5 — Frontend

### Task 5.1: Setup do Vitest

**Files:**
- Modify: `apps/web/package.json`
- Create: `apps/web/vitest.config.ts`

- [ ] **Step 1:** Adicionar devDeps: `vitest`, `@vitest/coverage-v8`. Script `"test": "vitest run"`.
- [ ] **Step 2:** `vitest.config.ts` com `environment: "node"` (os testes de SSE/hook de transporte não precisam DOM; para hooks usar `@testing-library/react` + `jsdom` só se necessário — começar node).

```ts
// apps/web/vitest.config.ts
import { defineConfig } from "vitest/config";
export default defineConfig({ test: { environment: "node" } });
```

- [ ] **Step 3:** `cd apps/web && npm install` · Expected: ok
- [ ] **Step 4:** Commit `git commit -m "test(web): setup vitest"`

### Task 5.2: `lib/sse.ts` — parser SSE tipado (extraído de api.ts)

**Files:**
- Create: `apps/web/lib/sse.ts`
- Create: `apps/web/lib/chat-events.ts`
- Modify: `apps/web/lib/api.ts` (chatStream delega)
- Test: `apps/web/test/sse.test.ts`

**Interfaces:**
- Produces:
  - `chat-events.ts`: `type ApoloEvent = {type:"status",text} | {type:"classification",dominio,confidence} | {type:"sql",sql} | {type:"token",delta} | {type:"chart",tipo,spec} | {type:"done",...} | {type:"error",text}`.
  - `sse.ts`: `async function* parseSSE(stream: ReadableStream<Uint8Array>): AsyncGenerator<{event:string; data:any}>` — contém a lógica de buffer/normalização `\r\n`→`\n`/split `\n\n` HOJE em `api.ts:67-97` (cópia verbatim).

- [ ] **Step 1: Teste — parser separa eventos com CRLF**

```ts
// apps/web/test/sse.test.ts
import { describe, it, expect } from "vitest";
import { parseSSE } from "../lib/sse";

function streamFrom(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(c) { for (const ch of chunks) c.enqueue(enc.encode(ch)); c.close(); },
  });
}

describe("parseSSE", () => {
  it("separa eventos com CRLF e parseia JSON", async () => {
    const s = streamFrom([
      'event: message\r\ndata: {"type":"status","text":"oi"}\r\n\r\n',
      'event: message\r\ndata: {"type":"token","delta":"a"}\r\n\r\n',
    ]);
    const got: any[] = [];
    for await (const ev of parseSSE(s)) got.push(ev.data);
    expect(got).toEqual([{ type: "status", text: "oi" }, { type: "token", delta: "a" }]);
  });
});
```

- [ ] **Step 2:** Rodar — falha · `cd apps/web && npx vitest run test/sse.test.ts` · Expected: FAIL
- [ ] **Step 3:** Implementar `sse.ts` movendo o corpo do while de `api.ts` (linhas 67-97), recebendo `resp.body` e dando `yield` de `{event, data}`. `chat-events.ts` com a união de tipos.
- [ ] **Step 4:** `api.ts` `chatStream` passa a: `const resp = await fetch(...); if (!resp.ok||!resp.body) throw...; yield* parseSSE(resp.body);`
- [ ] **Step 5:** Rodar — passa · Expected: PASS
- [ ] **Step 6:** Commit `git commit -m "refactor(web): parser SSE tipado em lib/sse"`

### Task 5.3: `hooks/useChatTurn.ts` — máquina de estado do turno

**Files:**
- Create: `apps/web/hooks/useChatTurn.ts`
- Test: `apps/web/test/useChatTurn.test.ts`

> Extrair de `ChatPanel.tsx` toda a lógica que: chama `chatStream`, acumula tokens na mensagem corrente, atualiza os "passos" da pipeline (status/classification/sql), trata `error`/`done`, e a auto-criação de sessão + race-fix (`sessaoAutocriadaRef`).

**Interfaces:**
- Produces: `function useChatTurn(opts) => { messages, steps, status, enviar(pergunta), ... }`. A forma exata espelha o estado atual do `ChatPanel`. O teste alimenta um `chatStream` fake (injeção via parâmetro/opção) e assevera as transições.

- [ ] **Step 1:** Teste de transição (idle→streaming→done) consumindo um gerador fake de eventos.
- [ ] **Step 2:** Rodar — falha.
- [ ] **Step 3:** Implementar o hook movendo o estado do `ChatPanel`. Para testabilidade, o hook recebe a função de stream como dependência opcional (default = `chatStream` de `lib/api`).
- [ ] **Step 4:** Rodar — passa.
- [ ] **Step 5:** Commit `git commit -m "refactor(web): useChatTurn (estado do turno)"`

### Task 5.4: `hooks/useVoiceCall.ts`

**Files:**
- Create: `apps/web/hooks/useVoiceCall.ts`
- Test: `apps/web/test/useVoiceCall.test.ts`

> Encapsular o ciclo de `lib/realtime.ts` + nível de mic + mute que hoje está no `ChatPanel`/`VoiceCall`.

- [ ] **Step 1:** Teste do hook (start/stop/mute) com `realtime` fake.
- [ ] **Step 2-4:** TDD.
- [ ] **Step 5:** Commit `git commit -m "refactor(web): useVoiceCall"`

### Task 5.5: Fatiar `ChatPanel.tsx`

**Files:**
- Create: `apps/web/components/PipelineSteps.tsx`
- Create: `apps/web/components/Composer.tsx`
- Modify: `apps/web/components/ChatPanel.tsx` (vira composição)

- [ ] **Step 1:** Extrair a renderização dos passos para `PipelineSteps` (props: `steps`).
- [ ] **Step 2:** Extrair a caixa de input para `Composer` (props: `onEnviar`, `disabled`).
- [ ] **Step 3:** `ChatPanel` passa a usar `useChatTurn` + `useVoiceCall` + `PipelineSteps` + `Composer` + componentes de apresentação existentes. Alvo ≤ ~120 linhas.
- [ ] **Step 4:** Build do web + smoke manual:

Run: `cd apps/web && npm run build` · Expected: build ok
Run (manual): subir a stack, abrir localhost:3000, mandar pergunta, ligar voz · Expected: comportamento visual idêntico.

- [ ] **Step 5:** Commit `git commit -m "refactor(web): ChatPanel fino compondo hooks e subcomponentes"`

---

## FASE 6 — Limpeza e verificação final

### Task 6.1: Eval semântico (complementar, contra banco real)

**Files:**
- Create: `apps/api/tests/test_eval_semantico.py` (marcado `@pytest.mark.eval`, NÃO roda no build gate)

> Casos validados: Eduarda atrasadas=1, total empresa=16, Diego cadastrou 1 lead, Global Drones tem contato, "fechados" = Contrato Assinado. Cada caso roda o pipeline real contra a base e assevera a contagem na resposta. Requer `config.json` com credenciais — rodado sob demanda (`pytest -m eval`), não no CI.

- [ ] **Step 1:** Escrever os casos como asserts sobre o texto da resposta (regex de número).
- [ ] **Step 2:** Marcar `@pytest.mark.eval` e registrar o marker em `pyproject.toml`.
- [ ] **Step 3:** Rodar localmente com a stack no ar · Expected: verde.
- [ ] **Step 4:** Commit `git commit -m "test: eval semantico (sob demanda, fora do CI)"`

### Task 6.2: Verificação final + merge

- [ ] **Step 1:** Suíte completa: `cd apps/api && python -m pytest tests/ -q` · Expected: verde (exceto `-m eval`).
- [ ] **Step 2:** `cd apps/web && npm run test && npm run build` · Expected: verde.
- [ ] **Step 3:** Build gate: `cd apps/api && docker build --target test -t apolo-api-test .` · Expected: verde.
- [ ] **Step 4:** Stack + smoke das 4 perguntas-chave (Eduarda=1, lead hoje=1, contato Global Drones, fechados). Comparar com baseline.
- [ ] **Step 5:** Conferir métricas: `engine.py` é shim de 1 linha; nenhum estágio > ~60 linhas; orquestrador ≤ ~80; `ChatPanel.tsx` ≤ ~120.
- [ ] **Step 6:** Abrir PR de `arch/refatoracao-orquestrador` → `main` com checklist dos critérios de aceite do spec.

---

## Self-Review (cobertura do spec)

- §5 backend layout → Fases 1-4 (ports, context, events, errors, stages, orchestrator). ✔
- §6 frontend layout → Fase 5 (sse, hooks, ChatPanel slim). ✔
- §7 rede de segurança PRIMEIRO → Fase 0 (caracterização) antes de qualquer mudança de produção. ✔
- §7.4 eval semântico complementar/não-bloqueante → Task 6.1 (`-m eval`, fora do CI). ✔
- §3 contrato de preservação → invariante verificada em cada fase pela caracterização. ✔
- Inconsistência de erro (error_event vs token_stream) → preservada via `ApoloError.modo` (Task 2.3/4.1). ✔
- 3 formatos de `done` → preservados via `Done` opcional + `_done_event` mapeado (Task 2.2/4.1). ✔
- Retry fora do escopo → não há task de retry. ✔
- Não tocar `domains/*`/`sql_guard` lógica → só `montar_sql_final` é MOVIDO (Task 3.9), sem alterar corpo. ✔
