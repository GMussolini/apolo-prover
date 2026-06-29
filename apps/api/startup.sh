#!/usr/bin/env bash
# Startup do backend no Azure App Service (Linux, Python) — SEM Docker.
# O App Service Python NAO traz o ODBC Driver 18 (necessario pro pyodbc/aioodbc
# falar com o SQL Server). Este script instala o driver no boot e sobe o uvicorn.
# Configurar como "Startup Command" do Web App:  bash startup.sh
set -e

if ! odbcinst -q -d 2>/dev/null | grep -q "ODBC Driver 18"; then
  echo "[startup] instalando ODBC Driver 18 for SQL Server..."
  curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg
  echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
    > /etc/apt/sources.list.d/mssql-release.list
  apt-get update
  ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev
  echo "[startup] driver instalado."
fi

# App Service Linux proxeia 80/443 -> 8000.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
