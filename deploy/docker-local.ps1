$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
}

docker compose up -d --build
Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:8501"
