#!/bin/bash

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

jobs_forecast="model_linear model_linreg model_cilinear model_actuals model_gsheets model_mljar replicate_labor_role_hours_day_ratio replicate_portfolio_laborrole_forecast_sheet"
jobs_forecast_train="model_mljar_train"

jobs_tmkt=""
jobs_tmkt_train="tmkt_people_gptindex tmkt_chatdb_train tmkt_resumes_load_index tmkt_job_postings_load_index"
jobs_tmkt_test="tmkt_people_gptindex_test tmkt_people_gptindex_test_interactive tmkt_test_query_jobs"

jobs_chat="chat_test chat_core"

sections="core_often core_daily skills forecast forecast_train tmkt tmkt_train tmkt_test chat"


if [ "$1" = "" ]; then
    echo "Usage: $0 [section] or job [jobname]"
    echo ""
    for section in `echo $sections`; do
        eval "sectionlist=\$jobs_$section"
        echo "  $section: $sectionlist"
    done

elif [ "$1" = "job" ]; then
    python3 -m flask $2 2>&1 |tee -a $logfile

else

    for section in core_often core_daily skills forecast tmkt tmkt_test tmkt_test_train chat; do
        if [ "$1" = "$section" ]; then
            eval "sectionlist=\$jobs_$section"
            for function in `echo $sectionlist`; do
                python3 -m flask $function 2>&1 |tee -a $logfile
            done
        fi
    done

fi

