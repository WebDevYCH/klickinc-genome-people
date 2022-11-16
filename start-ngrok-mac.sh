#!/bin/sh

logfile=ngrok.log

# start ngrok proxy -- requires paid account if you want a fixed subdomain
#subd=`grep ngrok-subdomain config.txt |awk '{print $3}'`
subd=willergp

while true; do
	echo --------------------------------- |tee -a $logfile
	date |tee -a $logfile
	echo Starting up |tee -a $logfile
	if [ "$subd" = "" ] ; then
		ngrok http 6005
	else
		ngrok http --subdomain=$subd 6005
	fi
	echo Restarting in 5s |tee -a $logfile
	sleep 5
done

