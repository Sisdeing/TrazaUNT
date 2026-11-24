$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 iniciar.py
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python iniciar.py
} else {
    Write-Host 'Instala Python 3.11 o superior y activa el lanzador py.'
}
Read-Host 'Pulsa Enter para cerrar'
