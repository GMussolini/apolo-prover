# APOLO_PROVER

Instância APOLO (Musstins) pra Prover Tecnologia.

Chat conversacional (texto + voz Realtime) sobre as bases de produção:
- `BdD017CrmProver` — CRM comercial (PreLeads, Clients, Tarefas, Reuniões, Coordenador IA)
- `BdControleRecursos` — administrativo (ContasAPagar/Receber, Folhas, Projetos, Contratos)

## Stack

- **Backend:** FastAPI · Python 3.12 · aioodbc · psycopg 3 · sqlglot
- **Frontend:** Next.js 15 · Tailwind v4 · shadcn/ui · Vega-Lite
- **DB auditoria:** Postgres 16
- **LLMs:** Claude Sonnet 4.6 + Haiku 4.5 (texto) · OpenAI Realtime gpt-4o (voz)

## Subir local (dev)

```powershell
# 1. preparar config
cp config.example.json config.json
# editar config.json com:
#   - anthropic_api_key, openai_api_key
#   - senhas reais do CRM/CR (já populadas no example)
#   - jwt_secret (64 chars random; pode ser gerado pelo installer/setup.py)

# 2. subir docker
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# 3. abrir no browser
# API:  http://localhost:8000/health
# Web:  http://localhost:3000
```

## Estrutura

```
APOLO_PROVER/
├── apps/
│   ├── api/                 # FastAPI
│   │   ├── app/
│   │   │   ├── core/        # config, database, engine, sql_guard, rate_limiter, logging, migrations
│   │   │   ├── services/    # anthropic, realtime, pipeline, auth, prompts
│   │   │   ├── domains/     # 6 domínios cravados (Python files)
│   │   │   ├── prompts/     # 5 prompts cravados (.txt)
│   │   │   ├── api/         # rotas: chat, voice, auth, sessoes, health
│   │   │   ├── installer/   # setup inicial (secret JWT, seed usuários)
│   │   │   └── tools/       # CLIs (stats)
│   │   └── tests/
│   └── web/                 # Next.js 15
│       ├── app/             # routes: /, /login, /chat
│       ├── components/      # ChatPanel, VoiceBubble, etc
│       ├── lib/             # auth, api, realtime
│       └── styles/          # globals + theme APOLO azul
├── data/
│   ├── postgres/            # volume Postgres
│   ├── logs/                # JSON logs estruturados
│   └── backups/             # dumps Postgres
├── config.example.json
├── docker-compose.yml
├── docker-compose.dev.yml
└── README.md
```

## Docs

- **PRD v0:** `../CRM/D0.000.17 - CRM PROVER/Docs/APOLO_DISCOVERY/06-PRD-v0.md`
- **Plano executável:** `../CRM/D0.000.17 - CRM PROVER/Docs/superpowers/plans/2026-05-29-apolo-prover-v0.md`
- **Discovery das bases:** `../CRM/D0.000.17 - CRM PROVER/Docs/APOLO_DISCOVERY/`

## Os 6 domínios cravados (v0)

| Código | Base | Permissão | O que cobre |
|--------|------|-----------|-------------|
| `CRM_PIPELINE` | crm | aberto | Funil: PreLeads + Clients + FaseVenda + MotivoConclusao |
| `CRM_OPERACAO_VENDEDOR` | crm | aberto | Tarefas + AtividadesDiarias + Reuniões + Participantes |
| `CRM_COORDENADOR_IA` | crm | coordenador | Sprint 1-3 do Coordenador (Casos, Passos, Feedback, Regras) |
| `CR_FLUXO_CAIXA` | cr | financeiro | ContasAPagar + ContasAReceber + ContasFinanceiros |
| `CR_FOLHA_PESSOAS` | cr | rh | Folhas + Colaboradores + Cargos + Empréstimos + Cestas |
| `CR_DELIVERY` | cr | delivery | ProjetoEmpresaColaboradores + Contratos + Timesheet + Empresas |

## Comandos úteis

```powershell
# Stats últimos 7 dias
docker compose exec api python -m app.tools.stats --periodo=7

# Logs do API
docker compose logs -f api

# Backup Postgres
docker compose exec postgres pg_dump -U apolo apolo > data/backups/apolo-$(date +%Y%m%d).sql

# Rodar testes
docker compose exec api pytest -v
```
