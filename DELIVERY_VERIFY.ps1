$ErrorActionPreference = "Stop"
$root = (Resolve-Path $PSScriptRoot).Path

$unexpected = @(
    Get-ChildItem -LiteralPath $root -Recurse -File -Force |
        Where-Object {
            $_.Name -eq ".env" -or
            $_.Extension -in @(".db", ".sqlite", ".sqlite3", ".pyc") -or
            $_.FullName -match "__pycache__"
        }
)

if ($unexpected.Count -gt 0) {
    $unexpected | ForEach-Object { Write-Warning "发现不应交付的文件：$($_.FullName)" }
    throw "交付包包含运行时或密钥文件。"
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Warning "未找到 Python，跳过自动测试。源码和目录检查已通过。"
    exit 0
}

Push-Location $root
try {
    & $python.Source -B -m unittest discover -s tests -v
} finally {
    Pop-Location
}
