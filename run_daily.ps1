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
# Pull first: if anything landed on GitHub since the last run (even
# something unrelated, like a file added through the GitHub web UI),
# a bare push here gets silently rejected -- git prints an error but
# this script has no error-checking, so it would otherwise just move on
# and quietly leave the commit stuck local-only. That happened for real
# on 2026-07-18 when a .devcontainer file was added on GitHub: every run
# since then failed to push without anyone noticing, and Streamlit Cloud
# (which deploys from GitHub) kept serving days-old data as a result.
git pull --no-edit
git add paper_trades.csv paper_trade_results.csv
git commit -m "Automated scan update: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$pushOutput = git push 2>&1
Write-Host $pushOutput
if ($LASTEXITCODE -ne 0) {
    Write-Host "!!! GIT PUSH FAILED -- data is committed locally but NOT on GitHub/Streamlit. Check this log. !!!"
}

Write-Host "=== Daily run complete ==="

Stop-Transcript | Out-Null
