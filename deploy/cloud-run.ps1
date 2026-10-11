param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [string]$Region = "asia-east1",
    [string]$ServiceName = "sitesaha-ai",
    [string]$ApiKey = $env:SITESHAHA_LLM_API_KEY,
    [string]$AccessCode = $env:SITESHAHA_ACCESS_CODE
)

$ErrorActionPreference = "Stop"

if (-not $ApiKey) {
    throw "请先设置 SITESHAHA_LLM_API_KEY，或通过 -ApiKey 传入。"
}

gcloud config set project $ProjectId
gcloud run deploy $ServiceName `
    --source . `
    --region $Region `
    --allow-unauthenticated `
    --set-env-vars "SITESHAHA_LLM_MODE=on,SITESHAHA_LLM_BASE_URL=https://api.deepseek.com/v1,SITESHAHA_LLM_MODEL=deepseek-chat,SITESHAHA_LLM_API_STYLE=chat,SITESHAHA_ACCESS_CODE=$AccessCode,SITESHAHA_LLM_API_KEY=$ApiKey"
