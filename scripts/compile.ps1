# Compila cualquier archivo .tex pasado como argumento o todos los .tex en cvs/originals/
# Uso: .\scripts\compile.ps1 cvs\originals\cv_spanish_2025.tex
#       .\scripts\compile.ps1  (compila todos los .tex en cvs/originals/)

param(
    [string[]]$Files
)

# Siempre trabajar desde la raíz del proyecto (un nivel arriba de scripts/)
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot

try {
    if (-not $Files) {
        $Files = Get-ChildItem -Path "$projectRoot\cvs\originals" -Filter "*.tex" | Select-Object -ExpandProperty FullName
    }

    foreach ($file in $Files) {
        if (-not (Test-Path $file)) {
            Write-Host "No encontrado: $file" -ForegroundColor Red
            continue
        }
        Write-Host "`nCompilando $file ..." -ForegroundColor Cyan
        xelatex "-aux-directory=$env:TEMP" -interaction=nonstopmode $file
        if ($LASTEXITCODE -eq 0) {
            Write-Host "$file -> OK" -ForegroundColor Green
        } else {
            Write-Host "$file -> ERROR (ver log en $env:TEMP)" -ForegroundColor Red
        }
    }
} finally {
    Pop-Location
}
