<#
.SYNOPSIS
    Запускає сервіс каталогу маршрутів у потрібному режимі AI-компонента.

.DESCRIPTION
    Режим визначає, звідки береться пропозиція моделі:
      live    — справжній виклик провайдера (потрібен ключ у .env);
      stub    — підготовлені відповіді з stubs/responses.json (детерміновані перевірки);
      offline — імітація недоступності моделі (перевірка збою).

    Кожен режим використовує ОКРЕМЕ сховище, тому проходи не впливають один на
    один. Ключ провайдера потрібен лише серверу, notebook'ам він не потрібен.

.EXAMPLE
    .\scripts\serve.ps1 stub
.EXAMPLE
    .\scripts\serve.ps1 live
#>
param(
    [ValidateSet("live", "stub", "offline")]
    [string]$Mode = "stub",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$db = "data/test-routes-$Mode.json"
$env:ROUTE_LLM_MODE = $Mode
$env:ROUTES_DB = $db
$env:ROUTE_LLM_STUB = "stubs/responses.json"

Write-Host ""
Write-Host "  Режим AI-компонента : $Mode"
Write-Host "  Сховище             : $db"
Write-Host "  Адреса API          : http://127.0.0.1:$Port"
Write-Host ""
Write-Host "  Документація API: http://127.0.0.1:$Port/docs"
Write-Host "  Зупинити: Ctrl+C"
Write-Host ""

& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --port $Port
