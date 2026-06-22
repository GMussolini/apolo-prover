FROM python:3.12-slim AS base

# Postgres embutido (efemero, some quando o container reinicia) + ODBC SQL Server
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg unixodbc-dev g++ ca-certificates \
    postgresql postgresql-contrib \
    procps \
 && curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
 && echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update \
 && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Gate de build: o guardião de schema roda durante o build. Se algum domínio
#    referenciar tabela/coluna que não existe no dump real, este stage falha e
#    dev/prod (que dependem dele via COPY --from=test) nem são construídos.
#    pytest/tests ficam só aqui — não incham a imagem final. ──
FROM base AS test
COPY pyproject.toml .
COPY app /app/app
COPY tests /app/tests
RUN python -m pytest tests/test_catalog_consistency.py tests/test_characterization.py -q

FROM base AS dev
COPY --from=test /app/app /app/app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS prod
COPY --from=test /app/app /app/app
COPY boot.sh /boot.sh
RUN chmod +x /boot.sh
EXPOSE 8000
# boot.sh inicia o Postgres local efemero antes do uvicorn.
CMD ["/boot.sh"]
