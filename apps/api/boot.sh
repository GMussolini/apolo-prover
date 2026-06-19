#!/bin/bash
# Boot script - sobe Postgres local efemero + uvicorn no mesmo container.
# Postgres em /tmp/pgdata - some quando o pod reinicia ("em memoria" do POV do usuario).
set -e

PG_DATA="/tmp/pgdata"
# Detecta versao instalada (Debian 12 default = 15; resiste a upgrades)
PG_BIN="$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -n1)"
if [ -z "${PG_BIN}" ]; then
  echo "[boot] ERRO: postgresql nao encontrado em /usr/lib/postgresql/*/bin" >&2
  exit 1
fi
export PATH="${PG_BIN}:${PATH}"
echo "[boot] usando ${PG_BIN}"

if [ ! -d "${PG_DATA}/base" ]; then
  echo "[boot] inicializando cluster Postgres em ${PG_DATA}..."
  mkdir -p "${PG_DATA}"
  chown -R postgres:postgres "${PG_DATA}"
  su -s /bin/bash postgres -c "${PG_BIN}/initdb -D ${PG_DATA} --auth-local=trust --auth-host=trust --username=apolo -E UTF8"
  echo "host all all 127.0.0.1/32 trust" >> "${PG_DATA}/pg_hba.conf"
  echo "listen_addresses = '127.0.0.1'" >> "${PG_DATA}/postgresql.conf"
  echo "unix_socket_directories = '/tmp'"  >> "${PG_DATA}/postgresql.conf"
fi

echo "[boot] startando Postgres..."
su -s /bin/bash postgres -c "${PG_BIN}/pg_ctl -D ${PG_DATA} -l /tmp/pg.log -o '-k /tmp' start"

echo "[boot] aguardando Postgres aceitar conexao..."
for i in $(seq 1 30); do
  if ${PG_BIN}/pg_isready -h 127.0.0.1 -p 5432 -U apolo >/dev/null 2>&1; then
    echo "[boot] Postgres pronto."
    break
  fi
  sleep 1
done

# Cria DB 'apolo' se nao existe (initdb cria role apolo e DB postgres apenas)
${PG_BIN}/psql -h 127.0.0.1 -U apolo -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='apolo'" | grep -q 1 \
  || ${PG_BIN}/createdb -h 127.0.0.1 -U apolo apolo

echo "[boot] iniciando uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
