param(
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path $PSScriptRoot).Path

$targets = @(
    (Join-Path $root ".env"),
    (Join-Path $root "data\sitesaha.db"),
    (Join-Path $root "data\sitesaha.db-shm"),
    (Join-Path $root "data\sitesaha.db-wal"),
    (Join-Path $root "data\test-web.db"),
    (Join-Path $root "data\uploads")
)

$cacheDirectories = Get-ChildItem -LiteralPath $root -Recurse -Directory -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq "__pycache__" }
$cacheFiles = Get-ChildItem -LiteralPath $root -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in @(".pyc", ".pyo", ".log") }

if (-not $Apply) {
    Write-Host "以下内容将被清理："
    $targets | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object { Write-Host "  $_" }
    $cacheDirectories | ForEach-Object { Write-Host "  $($_.FullName)" }
    $cacheFiles | ForEach-Object { Write-Host "  $($_.FullName)" }
    Write-Host "`n预览完成。确认后运行：.\DELIVERY_CLEANUP.ps1 -Apply"
    exit 0
}

foreach ($target in $targets) {
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
        Write-Host "已删除 $target"
    }
}

foreach ($directory in $cacheDirectories) {
    if (Test-Path -LiteralPath $directory.FullName) {
        Remove-Item -LiteralPath $directory.FullName -Recurse -Force
        Write-Host "已删除 $($directory.FullName)"
    }
}

foreach ($file in $cacheFiles) {
    if (Test-Path -LiteralPath $file.FullName) {
        Remove-Item -LiteralPath $file.FullName -Force
        Write-Host "已删除 $($file.FullName)"
    }
}

Write-Host "清理完成。"
