param([string]$Root = "")

# PowerShell 脚本语法校验：解析交付根下的三个 .ps1，报告真实语法错误。
# 用法：powershell -NoProfile -File check_ps1.ps1 [-Root <交付根>]

if (-not $Root) {
    $Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..\..")).Path
}

$targets = @("PUSH_AND_DEPLOY.ps1", "VERIFY_ONLINE.ps1", "GO_ONLINE.ps1")
$failed = 0

foreach ($name in $targets) {
    $path = Join-Path $Root $name
    if (-not (Test-Path -LiteralPath $path)) {
        Write-Host "[跳过] $name 不存在"
        continue
    }
    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$tokens, [ref]$errors) | Out-Null
    if ($errors -and $errors.Count -gt 0) {
        Write-Host "[语法错误] $name"
        foreach ($e in $errors) { Write-Host ("   行 {0}: {1}" -f $e.Extent.StartLineNumber, $e.Message) }
        $failed += 1
    } else {
        Write-Host "[OK] $name 语法通过（$($tokens.Count) 个记号）"
    }
}

if ($failed -gt 0) {
    Write-Host ""
    Write-Host "$failed 个脚本存在语法错误"
    exit 1
}
Write-Host ""
Write-Host "全部 PowerShell 脚本语法通过"
exit 0
