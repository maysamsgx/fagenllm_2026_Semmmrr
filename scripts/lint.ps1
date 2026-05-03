
Write-Host "--- Running Ruff Linting ---" -ForegroundColor Cyan
python -m ruff check .

Write-Host "--- Running Mypy Type Checking ---" -ForegroundColor Cyan
python -m mypy . --ignore-missing-imports

Write-Host "--- Running Bandit Security Analysis ---" -ForegroundColor Cyan
python -m bandit -r . -x ./venv,./tests
