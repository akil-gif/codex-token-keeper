$env:ADMIN_PASSWORD="admin123"
$env:DATA_DIR="$(Split-Path $MyInvocation.MyCommand.Path)\data"
$env:SCHEDULER_INTERVAL_SECONDS="1800"
$env:REFRESH_THRESHOLD_SECONDS="86400"
$env:PROXY_URL=""
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
