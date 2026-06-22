# Refatoração de Arquitetura — Decomposição do Orquestrador

**Data:** 2026-06-22
**Branch:** `arch/refatoracao-orquestrador`
**Tipo:** Refatoração estrutural pura (organização de código). **ZERO funcionalidade nova.**

---

## 1. Objetivo

Reduzir a dívida estrutural do APOLO_PROVER tornando o código **testável, decomposto e
extensível** — sem alterar **nada** do comportamento observável. Hoje o sistema funciona; o
problema é que ele é difícil de evoluir com segurança porque a orquestração está concentrada
em duas "funções-deus" (uma no backend, uma no frontend) que misturam muitas responsabilidades
e não têm rede de teste.

## 2. Não-objetivos (escopo NEGATIVO — explícito)

Esta refatoração **NÃO** inclui, sob nenhuma hipótese:

- ❌ Nenhuma funcionalidade nova (sem estágio "crítico/verificador", sem abstenção, sem novo
  domínio, sem novo endpoint, sem mudança de UI).
- ❌ Nenhuma mudança de comportamento observável — mesmas respostas, mesmos eventos, mesma ordem,
  mesmos textos de erro, mesma latência (dentro de variação normal).
- ❌ Nenhuma mudança de regra de negócio / SQL / domínios (`domains/*` ficam intactos).
- ❌ Nenhuma otimização de performance que não seja consequência natural da reorganização.
- ❌ Nenhuma mudança de dependências, schema de banco, contrato de API HTTP ou formato SSE no fio.

Se durante a execução surgir a tentação de "já que estou aqui, adiciono X" — **não.** Vira item
de backlog separado.

## 3. Contrato de preservação (a invariante)

> **A sequência de eventos SSE emitida para qualquer pergunta deve ser idêntica, byte-a-byte,
> à do código atual.**

Isso é verificável e é a espinha dorsal da segurança da refatoração (ver §7).

---

## 4. Estado atual (a dívida)

### Backend
- `app/core/engine.py` — `processar_pergunta` é um gerador assíncrono de ~350 linhas que mistura
  8 responsabilidades: rate-limit, histórico, classificação, permissão, geração de SQL, montagem,
  execução, resposta (texto/voz), persistência **e** formatação dos eventos SSE.
- O bloco `try/except → log → estado["erro"] → yield erro → _persistir → yield done → return`
  está **copiado ~7 vezes**, com mensagens de erro ad-hoc espalhadas e sem taxonomia.
- Os "6 estágios" existem só no docstring, não no código. Não há como testar um estágio isolado.
- `estado` é um `dict` mutável solto, compartilhado por closure.
- Chamadas de LLM (`anthropic_service`) e execução de SQL (`database.execute_query`) são acopladas
  diretamente — impossível fakear em teste sem subir banco e gastar token.
- Sem retry/backoff nas chamadas de LLM (um 529 "overloaded" vira falha direta).

### Frontend
- `apps/web/components/ChatPanel.tsx` — 435 linhas. Espelho exato do problema: consome/parseia o
  stream SSE, máquina de estados do turno, auto-criação de sessão + race-fix, estado de voz, passos
  da pipeline **e** renderização — tudo num componente.
- A lógica de transporte (`lib/api.ts`, normalização de `\r\n`, split de eventos) está acoplada à view.

### O que está BOM e será preservado intacto
- Camadas `api / core / domains / services / schema_catalog`.
- A abstração declarativa de domínio (`domains/_base.py`: `Dominio`/`Ramo`/`Coluna`/`FewShot`).
- O `sql_guard` como fronteira de segurança (LLM nunca compõe JOIN/tabela).
- A persistência de tokens/custo/latência/erro por pergunta no Postgres.

---

## 5. Arquitetura-alvo — Backend

Padrão: **pipeline linear de estágios + contexto tipado + ports cirúrgicos** (não hexagonal
completo — ports só nas dependências externas que precisam ser fakeadas em teste).

```
app/
  pipeline/                  ← NOVO (absorve a orquestração que estava em engine.py)
    __init__.py
    context.py     # TurnContext (dataclass): usuario, sessao_id, pergunta, canal +
                   #   acumuladores (tokens_input/output, custo, t0) + snapshot de estado
    events.py      # eventos SEMÂNTICOS tipados: Status, Classification, Sql, Token,
                   #   Chart, Done, ErrorEvent  (independentes do formato SSE no fio)
    errors.py      # taxonomia ApoloError: RateLimited, ClassifyFailed, Unauthorized,
                   #   LowConfidence, SqlGenFailed, SqlBlocked, SqlExecFailed, AnswerFailed.
                   #   Cada uma carrega (mensagem_amigavel, codigo_log). Uma classe = um motivo.
    orchestrator.py# roda os estágios em ordem; trata erro→evento + persistência + done UMA vez
    stages/
      __init__.py
      rate_limit.py
      history.py
      classify.py
      authorize.py
      generate_sql.py
      assemble_sql.py   # delega ao pipeline.montar_sql_final atual (renomeado p/ sql_builder)
      execute_sql.py
      answer.py         # texto + voz unificados, parametrizado por canal
  ports/                     ← NOVO (interfaces p/ testar com fakes)
    __init__.py
    llm.py         # Protocol: chat_json / chat_texto      (adapter = anthropic_service)
    sql_exec.py    # Protocol: execute_query                (adapter = database.execute_query)
    turn_store.py  # Protocol: load_history / save_turn     (adapter = postgres)
```

### Forma de um estágio
Cada estágio é uma unidade pequena (~15-40 linhas) com interface uniforme:

```python
async def run(ctx: TurnContext, deps: Deps) -> AsyncIterator[Event]:
    # ...computa, pode yield Status/Token...
    # em falha terminal: raise ApoloError-subclass
    # em short-circuit "responde sem SQL" (baixa confiança, permissão negada):
    #   yield os tokens da resposta e raise TurnFinished
```

- `deps` agrega os ports (llm, sql_exec, turn_store) + `config`. Injetado pelo orquestrador.
- Short-circuits que hoje são `return` no meio do monólito viram sinais de controle explícitos
  (`TurnFinished`) — não são erros, produzem resposta normal.

### Orquestrador (alvo: ~60 linhas)
```python
async def processar_pergunta(...) -> AsyncIterator[dict]:
    ctx = TurnContext(...)
    deps = Deps(llm=AnthropicAdapter(), sql=SqlAdapter(), store=PgAdapter(), cfg=get_config())
    try:
        for stage in STAGES:                 # lista ordenada
            async for ev in stage.run(ctx, deps):
                yield ev
    except TurnFinished:
        pass                                 # resposta já emitida pelo estágio
    except ApoloError as e:
        ctx.erro = e.codigo_log
        yield ErrorEvent(e.mensagem_amigavel)
    finally:
        await deps.store.save_turn(ctx)      # persistência: UMA vez
        yield Done(ctx.metricas())
```

Os 7 `except` copiados colapsam nessa única política. `engine.py` deixa de existir como monólito
(seus helpers `_carregar_historico`, `_df_para_amostra`, etc. migram para os estágios/adapters
correspondentes).

### Decoupling SSE
O pipeline emite eventos **semânticos** (`events.py`). Um adaptador fino
(`pipeline/sse_render.py` ou dentro de `chat_routes.py`) traduz evento semântico → `{event, data}`
do fio. Como hoje o `chat_routes` já faz `json.dumps(evt, default=str)` sobre dicts, o alvo é manter
o **mesmo dict no fio** — o `Event` tipado tem um `.to_wire()` que produz exatamente o dict atual.
Isso garante o contrato de preservação e, de quebra, permite que a suíte de teste consuma os eventos
semânticos sem reparsear SSE.

### Retry/backoff — FORA DO ESCOPO (backlog)
**Decidido em 2026-06-22:** retry/backoff nas chamadas de LLM **não** faz parte desta refatoração.
Por ser o único item que alteraria comportamento (em caso de falha transiente 429/503/529), vai pro
backlog para manter a entrega 100% sem mudança de comportamento. O adapter de LLM (`ports/llm.py`)
fica desenhado de forma que adicionar retry depois seja trivial (um único ponto), mas a implementação
do retry NÃO entra agora.

---

## 6. Arquitetura-alvo — Frontend

```
apps/web/
  lib/
    sse.ts          # cliente SSE tipado: async-iterator de ApoloEvent
                    #   (move a normalização \r\n + split de api.ts para cá)
    chat-events.ts  # união de tipos espelhando events.py do backend
  hooks/
    useChatTurn.ts  # máquina de estados do turno: idle → classificando → gerando →
                    #   consultando → respondendo → done/erro. Expõe {messages, steps, send, status}
    useVoiceCall.ts # encapsula o ciclo de realtime.ts + nível de mic + mute
  components/
    ChatPanel.tsx   # FINO: compõe useChatTurn + useVoiceCall + subcomponentes
    PipelineSteps.tsx  # extraído do ChatPanel (apresentação dos passos)
    Composer.tsx       # extraído do ChatPanel (caixa de input + envio)
    # ChatMessage, ChartRenderer, VoiceCall, SessoesSidebar etc. permanecem
```

`ChatPanel` cai de 435 linhas para ~100 de composição. `lib/realtime.ts` (167 linhas) permanece como
camada de WebRTC, apenas consumida pelo `useVoiceCall`. Mesma renderização final, mesmos estados visuais.

---

## 7. Estratégia de testes — a rede de segurança (executada PRIMEIRO)

1. **Caracterização (backend)** — antes de mexer numa linha de produção: escrever testes que rodam o
   `processar_pergunta` **atual** com os ports fakeados (respostas de LLM e resultados de SQL gravados
   como fixtures determinísticas) e capturam um *snapshot* da sequência de eventos para ~15 perguntas
   representativas (contagem, ranking, baixa confiança, permissão negada, SQL bloqueado, erro de
   execução, voz, etc.). Roda no CI, sem rede, sem banco, sem token.
2. **Refatorar sob a rede** — cada passo da decomposição deve manter o snapshot idêntico. Divergência
   = falha de build.
3. **Caracterização (frontend)** — testes de `useChatTurn` alimentados por um stream SSE gravado,
   asseverando as transições de estado e a lista final de mensagens/passos.
4. **Eval semântico (complementar, contra banco real)** — os casos já validados (Eduarda=1,
   Diego cadastrou 1 lead, Global Drones tem contato, "fechados"=Contrato Assinado, total empresa=16…)
   viram suíte golden. *Não bloqueia a refatoração; é a rede de regressão de negócio de longo prazo.*

> Os testes capturam o comportamento **existente**. Não introduzem funcionalidade — são o instrumento
> que prova que a refatoração preservou tudo.

---

## 8. Sequência de execução (fases)

1. **Fase 0 — Rede:** fixtures + testes de caracterização do backend sobre o código atual (verde antes
   de qualquer refatoração).
2. **Fase 1 — Ports + adapters:** extrair `ports/` e envolver `anthropic_service` / `execute_query` /
   persistência em adapters. Engine passa a usar os adapters (comportamento idêntico). Snapshot verde.
3. **Fase 2 — TurnContext + events + errors:** introduzir o contexto tipado e os eventos/erros
   semânticos; `engine` passa a produzi-los e o `chat_routes` a renderizá-los no mesmo dict de fio.
4. **Fase 3 — Estágios:** mover cada bloco do monólito para `stages/*` um a um, rodando o snapshot a
   cada movimento. Orquestrador encolhe.
5. **Fase 4 — Política única de erro/persistência:** colapsar os 7 `except` na política do orquestrador.
6. **Fase 5 — Frontend:** extrair `lib/sse.ts`, `useChatTurn`, `useVoiceCall`, fatiar `ChatPanel`.
   Teste de caracterização do hook verde.
7. **Fase 6 — Limpeza:** remover código morto, atualizar imports, rodar suíte completa + build gate
   do catálogo + subir a stack e fazer smoke manual das mesmas perguntas.

Cada fase é um commit (ou poucos) na branch, sempre com a suíte verde. `main` permanece intocado até
o merge final.

## 9. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Refatorar quebra comportamento silenciosamente | Snapshot de eventos byte-a-byte; build falha na divergência |
| Mover estágio altera ordem/timing de eventos | Mover um estágio por commit, snapshot a cada passo |
| `montar_sql_final` / `sql_guard` mudarem semântica | Não tocados; só movidos/renomeados, cobertos por teste existente |
| Frontend muda render sutilmente | Subcomponentes apresentacionais preservados; só extração de estado |
| Retry introduzir comportamento novo | Fora do escopo (backlog) — não implementado nesta entrega |
| Escopo "rastejar" para features | §2 explícito; qualquer ideia nova vira backlog |

## 10. Critérios de aceite

- [ ] Suíte de caracterização (backend + frontend) verde, mesma sequência de eventos do código atual.
- [ ] `engine.py` monolítico eliminado; orquestrador ≤ ~80 linhas; nenhum estágio > ~60 linhas.
- [ ] Os 7 `except` colapsados em uma política única.
- [ ] `ChatPanel.tsx` ≤ ~120 linhas; transporte SSE em `lib/sse.ts`; estado em hooks.
- [ ] Build gate do catálogo verde; stack sobe; smoke manual idêntico (Eduarda=1 etc.).
- [ ] Zero mudança em `domains/*`, contrato HTTP/SSE no fio, schema de banco.
