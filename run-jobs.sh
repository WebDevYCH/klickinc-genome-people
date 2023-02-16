#!/bin/sh

logfile=../logs/run-jobs-$1-$2.log

# start webapp/webhook-receiver (move to port 6000 to get away from Mac airplay issues)
export FLASK_APP=app
export FLASK_DEBUG=1
export PYTHONPATH=.
export GOOGLE_APPLICATION_CREDENTIALS="../keys/google-key.json"
cd app

set -e

jobs_core_often="replicate_users replicate_userphotos replicate_portfolios replicate_portfolioforecasts"
jobs_core_daily="replicate_laborroles replicate_laborrolehc"
jobs_skills="replicate_skills"
jobs_forecast="model_linear model_linreg model_cilinear model_actuals model_gsheets model_mljar model_blend replicate_labor_role_hours_day_ratio replicate_portfolio_laborrole_forecast_sheet"
jobs_tmkt="tmkt_people_test"
jobs_train="train_automl_model tmkt_people_index tmkt_people_interactive tmkt_people_finetune_create tmkt_chatdb_train"
jobs_chat="chat_test chat_core"


if [ "$1" = "" ]; then
    echo "Usage: $0 [often|daily|forecast] or job [jobname]"
    echo ""
    echo " core often jobs: $jobs_core_often"
    echo " core daily jobs: $jobs_core_daily"
    echo " skills jobs:     $jobs_skills"
    echo " forecast jobs:   $jobs_forecast"
    echo " talent mkt jobs: $jobs_tmkt"
    echo " train jobs:      $jobs_train"
    echo " chat jobs:       $jobs_chat"

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

elif [ "$1" = "tmkt" ]; then
    for function in `echo $jobs_tmkt`; do
        python3 -m flask $function 2>&1 |tee -a $logfile
    done

elif [ "$1" = "train" ]; then
    for function in `echo $jobs_train`; do
        python3 -m flask $function 2>&1 |tee -a $logfile
    done

else
    echo "Unknown parameter: $1"


fi


