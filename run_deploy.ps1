$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
Write-Host '已准备 .env。请先编辑 .env 填入 SITESHAHA_LLM_API_KEY 和 SITESHAHA_ACCESS_CODE。'
Write-Host '启动：docker compose up -d --build'
Write-Host '访问：http://127.0.0.1:8501'
