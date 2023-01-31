$logfile = "logs/ngrok.log"
$subd = "genomep"

while ($true) {
    Write-Output "---------------------------------" | Out-File -Append $logfile
    Write-Output (Get-Date) | Out-File -Append $logfile
    Write-Output "Starting up" | Out-File -Append $logfile

    if ([string]::IsNullOrEmpty($subd)) {
        ngrok http 6005
    } else {
        ngrok http --subdomain=$subd 6005
    }

    Write-Output "Restarting in 5s" | Out-File -Append $logfile
    Start-Sleep -Seconds 5
}