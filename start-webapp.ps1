$logfile = "..\logs\webapp-mac.log"

$env:FLASK_APP = "app"
$env:FLASK_DEBUG = "1"
$env:PYTHONPATH = "."
$env:GOOGLE_APPLICATION_CREDENTIALS = "..\keys\google-key.json"
cd app

while ($true) {
& python.exe -m flask run -p 6005 *>&1 | Tee-Object -Append -FilePath $logfile
Write-Output "Restarting..."
Start-Sleep -Seconds 15
}
cd ..
