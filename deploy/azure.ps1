# =====================================================================
# Deploy do APOLO Prover no Azure Container Apps (ACA).
# Stack proprio (NAO confundir com o apolo da Dinisa em rg-apolo-dev/apolo-rg).
#
# Pre-requisitos:
#   - az CLI logado (az login) na subscription certa
#   - Docker Desktop rodando (build local + push pro ACR)
#   - config.json preenchido na raiz do repo (Anthropic+OpenAI+conns SQL+jwt+usuarios)
#
# Uso:  pwsh deploy/azure.ps1
#
# O backend recebe a config inteira via secret base64 (APOLO_CONFIG_B64) — nada
# de segredo no image. O Postgres de auditoria sobe como container app interno
# (TCP, efemero — para persistir, anexar Azure Files; ver nota no fim).
# =====================================================================
$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING   = "utf-8"

# ---- parametros ----
$RG   = "rg-apolo-prover-dev"
$LOC  = "brazilsouth"
$ACR  = "apoloproverreghbr"
$ENVN = "apolo-prover-env"
$PGPWD = "ApoloProver2025DB"          # senha do postgres interno (so rede interna)
$REPO = Split-Path -Parent $PSScriptRoot   # raiz do repo (deploy/ esta dentro)

# ---- 1. base: RG + ACR + ambiente ACA ----
az group create -n $RG -l $LOC | Out-Null
az acr create   -n $ACR -g $RG --sku Basic --admin-enabled true | Out-Null
az containerapp env create -n $ENVN -g $RG -l $LOC | Out-Null
$DOM = az containerapp env show -n $ENVN -g $RG --query "properties.defaultDomain" -o tsv
Write-Host "Ambiente: $DOM"

$acrUser = az acr credential show -n $ACR --query username -o tsv
$acrPwd  = az acr credential show -n $ACR --query "passwords[0].value" -o tsv
az acr login -n $ACR | Out-Null

# ---- 2. Postgres interno (TCP). Para apps no mesmo env: host = NOME-DO-APP:porta ----
az containerapp create -n apolo-prover-postgres -g $RG --environment $ENVN `
  --image postgres:16 --ingress internal --transport tcp --target-port 5432 --exposed-port 5432 `
  --env-vars POSTGRES_USER=apolo POSTGRES_PASSWORD=$PGPWD POSTGRES_DB=apolo `
  --cpu 0.5 --memory 1.0Gi --min-replicas 1 --max-replicas 1 | Out-Null

# ---- 3. config de producao -> base64 (postgres aponta pro app interno; CORS = frontend) ----
$cfg = Get-Content "$REPO\config.json" -Raw | ConvertFrom-Json
$cfg.postgres_conn = "postgresql://apolo:$PGPWD@apolo-prover-postgres:5432/apolo"
$cfg.cors_origins  = @("https://apolo-prover-frontend.$DOM", "http://localhost:3000")
$json = $cfg | ConvertTo-Json -Depth 12 -Compress
$b64  = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($json))

# ---- 4. backend: build local (roda o gate do guardiao) + push + container app ----
docker build -f "$REPO\apps\api\Dockerfile" -t "$ACR.azurecr.io/apolo-prover-backend:v1" "$REPO\apps\api"
docker push "$ACR.azurecr.io/apolo-prover-backend:v1"
az containerapp create -n apolo-prover-backend -g $RG --environment $ENVN `
  --image "$ACR.azurecr.io/apolo-prover-backend:v1" `
  --registry-server "$ACR.azurecr.io" --registry-username $acrUser --registry-password $acrPwd `
  --secrets "config-b64=$b64" --env-vars APOLO_CONFIG_B64=secretref:config-b64 `
  --ingress external --target-port 8000 --cpu 1.0 --memory 2.0Gi --min-replicas 1 --max-replicas 1 | Out-Null

# ---- 5. frontend: build com a URL do backend assada (NEXT_PUBLIC_API_URL) + push + app ----
$BACK = "https://apolo-prover-backend.$DOM"
docker build -f "$REPO\apps\web\Dockerfile" --build-arg NEXT_PUBLIC_API_URL=$BACK `
  -t "$ACR.azurecr.io/apolo-prover-frontend:v1" "$REPO\apps\web"
docker push "$ACR.azurecr.io/apolo-prover-frontend:v1"
az containerapp create -n apolo-prover-frontend -g $RG --environment $ENVN `
  --image "$ACR.azurecr.io/apolo-prover-frontend:v1" `
  --registry-server "$ACR.azurecr.io" --registry-username $acrUser --registry-password $acrPwd `
  --ingress external --target-port 3000 --cpu 0.5 --memory 1.0Gi --min-replicas 1 --max-replicas 1 | Out-Null

Write-Host ""
Write-Host "APOLO Prover no ar:"
Write-Host "  Frontend: https://apolo-prover-frontend.$DOM"
Write-Host "  Backend : $BACK/health"

# =====================================================================
# RE-DEPLOY (so atualizar codigo, sem recriar recursos):
#   docker build/push as imagens :v1 (passos 4 e 5) e:
#     az containerapp update -n apolo-prover-backend  -g rg-apolo-prover-dev --image .../apolo-prover-backend:v1  --revision-suffix vN
#     az containerapp update -n apolo-prover-frontend -g rg-apolo-prover-dev --image .../apolo-prover-frontend:v1 --revision-suffix vN
#   Mudou a config.json? Refaca o $b64 (passo 3) e:
#     az containerapp secret set -n apolo-prover-backend -g rg-apolo-prover-dev --secrets "config-b64=$b64"
#     az containerapp update     -n apolo-prover-backend -g rg-apolo-prover-dev --revision-suffix vN
#
# PERSISTIR o Postgres (hoje efemero — perde historico no restart):
#   criar storage account + file share, anexar como storage no env
#   (az containerapp env storage set) e montar volume Azure Files em
#   /var/lib/postgresql/data no apolo-prover-postgres.
# =====================================================================
