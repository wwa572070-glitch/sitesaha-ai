$ErrorActionPreference = "Stop"

$python = $env:PYTHON
if (-not $python) {
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) {
        $python = $command.Source
    }
}
if (-not $python) {
    $command = Get-Command py -ErrorAction SilentlyContinue
    if ($command) {
        $python = $command.Source
    }
}
if (-not $python) {
    throw "未找到 Python。请先安装 Python 3.10+，或设置 PYTHON 环境变量。"
}

& $python webapp.py @args
