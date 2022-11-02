#!/bin/sh

logfile=$0.log

# start webapp/webhook-receiver (move to port 6000 to get away from Mac airplay issues)
export FLASK_APP=webapp
export FLASK_ENV=development
flask run -p 6005 2>&1 |tee -a $logfile

