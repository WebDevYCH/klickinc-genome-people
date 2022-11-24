#!/bin/sh

logfile=$0.log

# start webapp/webhook-receiver (move to port 6000 to get away from Mac airplay issues)
export FLASK_APP=app
export FLASK_DEBUG=1
export PYTHONPATH=.
cd app

while /usr/bin/true; do
    python3 -m flask run -p 6005 2>&1 |tee -a $logfile
    sleep 15
done
cd ..

