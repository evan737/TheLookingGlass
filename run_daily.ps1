Set-Location "C:\Users\emras\kalshi-weather-bot"

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
git commit -m "Automated daily update: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
git push

Write-Host "=== Daily run complete ==="