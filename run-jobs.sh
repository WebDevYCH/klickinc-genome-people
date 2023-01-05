#!/bin/sh

logfile=$0-$1.log

# start webapp/webhook-receiver (move to port 6000 to get away from Mac airplay issues)
export FLASK_APP=app
export FLASK_DEBUG=1
export PYTHONPATH=.
export GOOGLE_APPLICATION_CREDENTIALS="../keys/google-key.json"
cd app

set -e

jobs_core_often="replicate_userphotos replicate_portfolioforecasts"
jobs_core_daily="replicate_users replicate_portfolios replicate_laborroles"
jobs_skills="replicate_skills"
jobs_forecast="model_linear model_cilinear model_gsheets replicate_labor_role_hours_day_ratio replicate_portfolio_laborrole_forecast_sheet"
# forecast_gsheets not working yet


if [ "$1" = "" ]; then
    echo "Usage: $0 [often|daily|forecast] or job [jobname]"
    echo ""
    echo " core often jobs: $jobs_core_often"
    echo " core daily jobs: $jobs_core_daily"
    echo " skills jobs:     $jobs_skills"
    echo " forecast jobs:   $jobs_forecast"

elif [ "$1" = "job" ]; then
    python3 -m flask $2 2>&1 |tee -a $logfile

elif [ "$1" = "often" ]; then
    for function in `echo $jobs_core_often`; do
        python3 -m flask $function 2>&1 |tee -a $logfile
    done

elif [ "$1" = "daily" ]; then
    for function in `echo $jobs_core_daily`; do
        python3 -m flask $function 2>&1 |tee -a $logfile
    done

elif [ "$1" = "skills" ]; then
    for function in `echo $jobs_skills`; do
        python3 -m flask $function 2>&1 |tee -a $logfile
    done

elif [ "$1" = "forecast" ]; then
    for function in `echo $jobs_forecast`; do
        python3 -m flask $function 2>&1 |tee -a $logfile
    done


fi


