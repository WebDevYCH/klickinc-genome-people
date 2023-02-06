$logfile = "..\logs\run-jobs-$args[0]-$args[1].log"

$env:FLASK_APP = "app"
$env:FLASK_DEBUG = "1"
$env:PYTHONPATH = "."
$env:GOOGLE_APPLICATION_CREDENTIALS = "..\keys\google-key.json"

cd "app"

$jobs_core_often = "replicate_users replicate_userphotos replicate_portfolios replicate_portfolioforecasts"
$jobs_core_daily = "replicate_laborroles replicate_laborrolehc"
$jobs_skills = "replicate_skills"
$jobs_forecast = "model_linear model_linreg model_cilinear model_actuals model_gsheets model_mljar replicate_labor_role_hours_day_ratio replicate_portfolio_laborrole_forecast_sheet"
$jobs_tmkt = "tmkt_people_test"
$jobs_train = "tmkt_people_index tmkt_people_interactivetrain_automl_model tmkt_people_finetune_create tmkt_chatdb_train"
$jobs_chat = "chat_test chat_core"

if ($args.Count -eq 0) {
    Write-Host "Usage: $args[0] [often|daily|forecast] or job [jobname]"
    Write-Host ""
    Write-Host " core often jobs: $jobs_core_often"
    Write-Host " core daily jobs: $jobs_core_daily"
    Write-Host " skills jobs:     $jobs_skills"
    Write-Host " forecast jobs:   $jobs_forecast"
    Write-Host " talent mkt jobs: $jobs_tmkt"
    Write-Host " train jobs:      $jobs_train"
    Write-Host " chat jobs:       $jobs_chat"
}
elseif ($args[0] -eq "job") {
    python -m flask $args[1] *>&1 | Tee-Object -FilePath $logfile
}
elseif ($args[0] -eq "often") {
    foreach ($function in $jobs_core_often.Split(" ")) {
        python -m flask $function *>&1 | Tee-Object -FilePath $logfile
    }
}
elseif ($args[0] -eq "daily") {
    foreach ($function in $jobs_core_daily.Split(" ")) {
        python -m flask $function *>&1 | Tee-Object -FilePath $logfile
    }
}
elseif ($args[0] -eq "skills") {
    foreach ($function in $jobs_skills.Split(" ")) {
        python -m flask $function *>&1 | Tee-Object -FilePath $logfile
    }
}
elseif ($args[0] -eq "forecast") {
    foreach ($function in $jobs_forecast.Split(" ")) {
        python -m flask $function *>&1 | Tee-Object -FilePath $logfile
    }
}
elseif ($args[0] -eq "tmkt") {
    foreach ($function in $jobs_tmkt.Split(" ")) {
        python -m flask $function *>&1 | Tee-Object -FilePath $logfile
    }
}
elseif ($args[0] -eq "train") {
    foreach ($function in $jobs_train.Split(" ")) {
        python -m flask $function *>&1 | Tee-Object -FilePath $logfile
    }
}
