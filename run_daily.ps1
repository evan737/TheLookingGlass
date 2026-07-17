Set-Location "C:\Users\emras\kalshi-weather-bot"

# Every run writes its own timestamped log so Task Scheduler runs are
# debuggable after the fact -- Task Scheduler itself doesn't capture
# console output, so without this a silent failure (e.g. a hung git auth
# prompt, an expired API key) would leave no trace beyond a bare exit code.
$logDir = "C:\Users\emras\kalshi-weather-bot\logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}
$logFile = Join-Path $logDir ("run_{0}.log" -f (Get-Date -Format "yyyy-MM-dd_HHmmss"))

Start-Transcript -Path $logFile -Append | Out-Null

# Keep the last 30 days of logs and quietly prune anything older, so this
# folder doesn't grow forever.
Get-ChildItem -Path $logDir -Filter "run_*.log" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
    Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "=== Weather scan ==="
python paper_trade_scan.py

Write-Host "=== Jobless claims scan ==="
python claims_trade_scan.py $env:FRED_API_KEY

Write-Host "=== Tennis scan ==="
python tennis_trade_scan.py $env:ODDS_API_KEY

Write-Host "=== Futures scan (Kalshi vs Polymarket) ==="
python futures_trade_scan.py

Write-Host "=== Settling trades ==="
python settle_trades.py

Write-Host "=== Pushing updated data to GitHub ==="
git add paper_trades.csv paper_trade_results.csv
git commit -m "Automated scan update: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
git push

Write-Host "=== Daily run complete ==="

Stop-Transcript | Out-Null
