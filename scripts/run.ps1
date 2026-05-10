$branch = git rev-parse --abbrev-ref HEAD

switch ($branch) {
    "main"    { $env:ENVIRONMENT = "production" }
    "staging" { $env:ENVIRONMENT = "staging" }
    default   { $env:ENVIRONMENT = "development" }
}

Write-Host " Rama: $branch"
Write-Host "  Ambiente: $env:ENVIRONMENT"
Write-Host "  Iniciando StoneFixer backend..."

uvicorn main:app --reload --host 0.0.0.0 --port 8000